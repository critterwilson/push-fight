"""
Converts a GameSession into the JSON-serialisable dict the frontend consumes.

Kept separate from the engine so the engine never has to know about HTTP/WS.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.server.session import GameSession


def serialize_state(session: "GameSession") -> dict:
    """
    Return a fully-formed state dict for a session.

    Board layout: list of 10 rows, each a list of 4 cell dicts.
    Cell dict shape:
        { y, x, killZone, piece: {team, shape} | null, isAnchor }
    """
    game = session.game
    board = game.board
    anchor = board.anchor_pos  # (y, x) or (None, None)

    rows = []
    for y in range(10):
        row = []
        for x in range(4):
            piece_obj = board.pieces[y][x]
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

    is_ai_turn = (
        session.mode == "pvai"
        and game.current_player == session.ai_team
        and not game.game_over
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
    }
