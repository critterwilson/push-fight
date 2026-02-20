"""
Converts a ``GameSession`` into the JSON-serialisable dict the frontend consumes.

This module is the single translation layer between the engine's snake_case
Python world and the frontend's camelCase JavaScript world. Every field name
that crosses the wire is converted here (e.g. ``current_player`` becomes
``currentPlayer``).

Kept separate from the engine so the engine never has to know about HTTP/WS
conventions, and separate from the handlers so serialisation logic isn't
duplicated across multiple handler methods.

Design notes
------------
- The board is serialised as a 10x4 grid of cell dicts, each containing its
  coordinates, kill-zone status, piece data (if any), and anchor status.
- The ``piece`` dict includes a ``name`` field (e.g. ``"sleeve"``, ``"joint"``)
  in addition to ``team`` and ``shape``. This is required by the frontend's
  voice-control system, which references pieces by their unique names.
- ``isAiTurn`` is computed here rather than stored on the session, because it
  depends on multiple conditions (PvAI mode, current player, game not over,
  not in setup phase) that can change independently.
- ``placementStatus`` is always included so the frontend can render the setup
  UI without a separate API call.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.server.session import GameSession

# The canonical five-piece roster. Order matters — it defines the sequence
# shown in the setup UI's piece palette.
_PIECE_ROSTER = ['sleeve', 'lapel', 'belt', 'neck', 'joint']


def _unplaced_pieces(board, team: str) -> list[str]:
    """Return the names of pieces from ``_PIECE_ROSTER`` that the given team
    has not yet placed on the board.

    Used during the setup phase to show the player which pieces they still
    need to position.

    Args:
        board: The game's ``Board`` object.
        team: ``"white"`` or ``"black"``.

    Returns:
        List of unplaced piece names in roster order.
    """
    placed = {p.name for row in board.pieces for p in row if p and p.team == team}
    return [n for n in _PIECE_ROSTER if n not in placed]


def serialize_state(session: "GameSession") -> dict:
    """Build the complete state dict that the frontend expects.

    This is called after every state-mutating action (move, push, setup
    placement, save load) and on initial WebSocket connection. The returned
    dict is sent as-is over the wire — no further transformation happens.

    Board layout: list of 10 rows, each a list of 4 cell dicts.
    Cell dict shape::

        {
            "y": int,
            "x": int,
            "killZone": bool,
            "piece": {"team": str, "shape": str, "name": str} | None,
            "isAnchor": bool
        }

    Args:
        session: The game session to serialise.

    Returns:
        A JSON-serialisable dict with camelCase keys matching the frontend's
        expected contract.
    """
    game = session.game
    board = game.board
    anchor = board.anchor_pos  # (y, x) or (None, None)

    # Build the 10x4 board grid, converting each cell to a frontend-friendly dict.
    rows = []
    for y in range(10):
        row = []
        for x in range(4):
            piece_obj = board.pieces[y][x]
            # Include "name" alongside "team" and "shape" so the frontend's
            # voice-control system can identify pieces by their unique names.
            piece = (
                {"team": piece_obj.team, "shape": piece_obj.shape, "name": piece_obj.name}
                if piece_obj is not None
                else None
            )
            row.append(
                {
                    "y": y,
                    "x": x,
                    "killZone": board.is_kill_zone(y, x),
                    "piece": piece,
                    "isAnchor": anchor[0] is not None and anchor == (y, x),
                }
            )
        rows.append(row)

    # Determine whether the AI should act next. All four conditions must hold:
    # PvAI mode, AI's team is current, game isn't over, and we're past setup.
    is_ai_turn = (
        session.mode == "pvai"
        and game.current_player == session.ai_team
        and not game.game_over
        and not game.setup_mode
    )

    return {
        "sessionId": session.session_id,
        "board": rows,
        "currentPlayer": game.current_player,
        "movesMade": game.moves_made,
        "pushCompleted": game.push_completed,
        "canMove": game.can_move(),
        "canPush": game.can_push(),
        "gameOver": game.game_over,
        "winner": game.winner,
        "piecesPushedOff": game.pieces_pushed_off,
        "mode": session.mode,
        "aiTeam": session.ai_team if session.mode == "pvai" else None,
        "isAiTurn": is_ai_turn,
        "setupMode": game.setup_mode,
        # Always include placement status so the frontend can render the setup
        # UI without needing a separate endpoint.
        "placementStatus": {
            "white": {**game.get_placement_status("white"), "unplaced": _unplaced_pieces(board, "white")},
            "black": {**game.get_placement_status("black"), "unplaced": _unplaced_pieces(board, "black")},
        },
    }
