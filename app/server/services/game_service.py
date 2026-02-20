"""
Core game action logic — move, push, skip, and valid-action queries.

This service encapsulates the engine's game rules and provides a clean
interface for the handler layer.  It translates between the handler's
request parameters and the engine's method signatures, and handles
turn-switching after a successful push.

All methods that query valid actions perform ownership and phase checks
before delegating to the engine, raising ValueError for invalid input.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.server.session import GameSession, SessionManager


class GameService:
    """Business logic for game actions, wrapping the engine's GameState."""

    def __init__(self, session_manager: SessionManager):
        self._sessions = session_manager

    def get_session_or_raise(self, session_id: str) -> "GameSession":
        """Look up a session by ID; raises ValueError if not found."""
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError("Session not found")
        return session

    def create_game(self, mode: str, difficulty: str, player_color: str) -> "GameSession":
        """Create a new game session.

        The AI team is the opposite of the player's chosen color.
        """
        ai_team = "black" if player_color == "white" else "white"
        return self._sessions.create(mode=mode, difficulty=difficulty, ai_team=ai_team)

    def execute_move(self, session: "GameSession", from_pos: tuple, to_pos: tuple) -> tuple[bool, str]:
        """Delegate a move action to the engine."""
        return session.game.perform_move(from_pos, to_pos)

    def execute_push(self, session: "GameSession", piece: tuple, direction: tuple) -> tuple[bool, str]:
        """Execute a push and auto-switch turns if the game isn't over.

        The turn switch happens here (not in the engine) because it's
        a server-level concern — the engine's perform_push only handles
        the physics of the push, not turn management.

        Returns:
            (success, message) tuple.
        """
        py, px = piece
        success = session.game.perform_push(py, px, direction)
        if not success:
            return False, "Invalid push"
        # Only switch turns if the game is still in progress
        if not session.game.game_over:
            session.game.switch_turn()
        return True, "Push executed"

    def skip_moves(self, session: "GameSession") -> None:
        """Force the move phase to end, advancing to the push phase.

        Sets moves_made to 2 (the maximum), so the player can only push.
        Raises ValueError if the game is over or push is already done.
        """
        game = session.game
        if game.game_over:
            raise ValueError("Game is already over")
        if game.push_completed:
            raise ValueError("Push already completed this turn")
        game.moves_made = 2

    def get_valid_moves(self, session: "GameSession", y: int, x: int) -> list[list[int]]:
        """Return valid move destinations for the piece at (y, x).

        Validates piece ownership and phase before querying the engine's
        BFS pathfinder.  Returns an empty list if the move phase is over.
        """
        game = session.game
        piece = game.board.get_piece(y, x)
        if not piece or piece == "OUT_OF_BOUNDS":
            raise ValueError("No piece at that position")
        if piece.team != game.current_player:
            raise ValueError("Not your piece")
        if not game.can_move():
            return []
        destinations = game.board.get_valid_moves(y, x)
        return [list(d) for d in destinations]

    def get_valid_pushes(self, session: "GameSession", y: int, x: int) -> list[list[int]]:
        """Return valid push direction vectors for the square piece at (y, x).

        Only square pieces can push.  Each direction [dy, dx] where the
        push chain doesn't run into a side rail is considered valid.
        """
        game = session.game
        piece = game.board.get_piece(y, x)
        if not piece or piece == "OUT_OF_BOUNDS":
            raise ValueError("No piece at that position")
        if piece.team != game.current_player:
            raise ValueError("Not your piece")
        if piece.shape != "square":
            raise ValueError("Only square pieces can push")

        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        valid: list[list[int]] = []
        for dy, dx in directions:
            _, landing = game.board.get_push_chain(y, x, dy, dx)
            # A push is valid if the landing spot is on the board
            # (side rails = out of bounds = blocked)
            if game.board.is_on_board(*landing):
                valid.append([dy, dx])
        return valid
