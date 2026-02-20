"""
Handlers for board-query endpoints (valid moves and valid pushes).

These read-only endpoints let the frontend request the set of legal
destinations for a selected piece (moves) or legal push directions
for a selected square piece (pushes).  The results are used to render
move-dot indicators and push-arrow overlays on the board.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from app.server.services.game_service import GameService


class QueryHandler:
    """Returns valid actions for a selected piece without mutating state."""

    def __init__(self, game_service: GameService):
        self.game = game_service

    def _get_session(self, session_id: str):
        """Look up a session or raise HTTP 404."""
        try:
            return self.game.get_session_or_raise(session_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Session not found")

    def valid_moves(self, session_id: str, y: int, x: int) -> dict:
        """Return all valid move destinations for the piece at (y, x)."""
        session = self._get_session(session_id)
        try:
            moves = self.game.get_valid_moves(session, y, x)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"moves": moves}

    def valid_pushes(self, session_id: str, y: int, x: int) -> dict:
        """Return all valid push direction vectors for the square piece at (y, x)."""
        session = self._get_session(session_id)
        try:
            directions = self.game.get_valid_pushes(session, y, x)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"directions": directions}
