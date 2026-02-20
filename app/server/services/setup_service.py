"""
Setup phase logic — piece placement, confirmation, and AI auto-placement.

During setup, each player places their 5 pieces on their half of the
board.  This service manages the placement workflow:

  1. **Place**: Put a named piece (e.g. 'sleeve') at a specific cell.
  2. **Remove**: Undo a placement (pick a piece back up).
  3. **Confirm**: Validate placement counts and advance.

In PvAI mode, the AI's pieces are auto-placed randomly after the human
confirms, and the game starts immediately.  In PvP mode, white confirms
first (switching to black for placement), then black confirms to start.

The PIECE_SHAPES mapping and SETUP_ROSTER tuple define the canonical
five-piece roster with their shapes, matching the BJJ theme.
"""

from __future__ import annotations
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.game_state import GameState
    from app.server.session import GameSession

# Mapping from piece name to shape — determines push eligibility
PIECE_SHAPES = {
    "sleeve": "square", "lapel": "square", "belt": "square",
    "neck": "round", "joint": "round",
}

# Ordered roster used for auto-placement (AI setup)
SETUP_ROSTER = [
    ("sleeve", "square"), ("lapel", "square"), ("belt", "square"),
    ("neck", "round"), ("joint", "round"),
]


class SetupService:
    """Handles piece placement during the setup phase."""

    def place_piece(self, session: "GameSession", name: str, y: int, x: int) -> None:
        """Place a named piece on the board during setup.

        Looks up the piece's shape from the roster and delegates to the
        engine's place_piece method.  Raises ValueError on any failure.
        """
        game = session.game
        if not game.setup_mode:
            raise ValueError("Game is not in setup mode")
        shape = PIECE_SHAPES.get(name)
        if shape is None:
            raise ValueError(f"Unknown piece name: {name}")
        success, message = game.place_piece(y, x, game.current_player, shape, name)
        if not success:
            raise ValueError(message)

    def remove_piece(self, session: "GameSession", y: int, x: int) -> None:
        """Remove a placed piece from the board (undo a placement).

        Raises ValueError if not in setup mode or no piece at the position.
        """
        game = session.game
        if not game.setup_mode:
            raise ValueError("Game is not in setup mode")
        success, message = game.remove_piece(y, x)
        if not success:
            raise ValueError(message)

    def confirm_placement(self, session: "GameSession") -> bool:
        """Confirm the current team's placement and advance the setup phase.

        Workflow:
          - PvAI: After human confirms, AI pieces are auto-placed and game starts.
          - PvP:  White confirms → switches to black.  Black confirms → game starts.

        Raises ValueError if the confirming team doesn't have exactly
        3 square + 2 round pieces placed.

        Returns:
            False (caller should check isAiTurn from the serialized state).
        """
        game = session.game
        if not game.setup_mode:
            raise ValueError("Game is not in setup mode")

        confirming_player = game.current_player
        valid, error = game._validate_team_placement(confirming_player)
        if not valid:
            raise ValueError(error)

        if session.mode == "pvai":
            # Auto-place AI pieces and start immediately
            self.auto_place(game, session.ai_team)
            game.start_game()
        elif confirming_player == "white":
            # White done — switch to black for their placement
            game.current_player = "black"
        else:
            # Black done — both teams placed, start the game
            game.start_game()

        return False

    def auto_place(self, game: "GameState", team: str) -> None:
        """Randomly place a full piece roster on a team's half of the board.

        Used for the AI opponent: shuffles all valid cells on the team's
        half and places one of each piece from the roster.
        """
        valid = [
            (y, x) for y in range(10) for x in range(4)
            if game._is_on_player_side(y, team) and game._is_playable_space(y, x)
        ]
        random.shuffle(valid)
        for (name, shape), (y, x) in zip(SETUP_ROSTER, valid):
            game.place_piece(y, x, team, shape, name)
