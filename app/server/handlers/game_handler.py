"""
Handlers for game lifecycle and action endpoints.

The GameHandler orchestrates the core gameplay loop:
  - Creating and retrieving game sessions
  - Executing moves (sliding pieces along empty cells)
  - Executing pushes (shoving piece chains with a square piece)
  - Skipping remaining moves to enter the push phase early

After each state-mutating action, the handler broadcasts the updated
state to all WebSocket subscribers and triggers the AI turn if applicable.
"""

from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.server.state_serializer import serialize_state

if TYPE_CHECKING:
    from app.server.services.ai_service import AIService
    from app.server.services.broadcast_service import BroadcastService
    from app.server.services.game_service import GameService


class GameHandler:
    """Orchestrates game service calls and translates errors to HTTP responses."""

    def __init__(self, game_service: GameService,
                 broadcast_service: BroadcastService,
                 ai_service: AIService):
        self.game = game_service
        self.broadcast = broadcast_service
        self.ai = ai_service

    def _get_session(self, session_id: str):
        """Look up a session or raise HTTP 404."""
        try:
            return self.game.get_session_or_raise(session_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Session not found")

    def _check_not_game_over(self, session):
        """Guard: reject actions on completed games."""
        if session.game.game_over:
            raise HTTPException(status_code=400, detail="Game is already over")

    def create_game(self, mode: str, difficulty: str, player_color: str) -> dict:
        """Create a new game session and return its initial state."""
        session = self.game.create_game(mode, difficulty, player_color)
        return {"sessionId": session.session_id, "state": serialize_state(session)}

    def get_game(self, session_id: str) -> dict:
        """Return the current state of an existing session."""
        session = self._get_session(session_id)
        return {"state": serialize_state(session)}

    async def make_move(self, session_id: str, from_pos, to_pos) -> dict:
        """Execute a piece move, broadcast the update, and return new state."""
        session = self._get_session(session_id)
        self._check_not_game_over(session)
        success, message = self.game.execute_move(session, tuple(from_pos), tuple(to_pos))
        if not success:
            raise HTTPException(status_code=400, detail=message)
        state = serialize_state(session)
        await self.broadcast.broadcast_state_update(session_id, state)
        return {"success": True, "message": message, "state": state}

    async def make_push(self, session_id: str, piece, direction) -> dict:
        """Execute a push, broadcast, and trigger AI turn if applicable.

        After a successful push ends the human's turn, if it's now the AI's
        turn, an async task is spawned to run the AI's moves and push.
        """
        session = self._get_session(session_id)
        self._check_not_game_over(session)
        success, message = self.game.execute_push(session, tuple(piece), tuple(direction))
        if not success:
            raise HTTPException(status_code=400, detail="Invalid push")
        state = serialize_state(session)
        await self.broadcast.broadcast_state_update(session_id, state)
        # Spawn AI turn as a background task so the HTTP response returns immediately
        if state["isAiTurn"]:
            asyncio.create_task(self.ai.run_ai_turn(session_id))
        return {"success": True, "message": "Push executed", "state": state}

    async def skip_moves(self, session_id: str) -> dict:
        """Skip remaining moves and advance directly to the push phase."""
        session = self._get_session(session_id)
        try:
            self.game.skip_moves(session)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        state = serialize_state(session)
        await self.broadcast.broadcast_state_update(session_id, state)
        return {"success": True, "state": state}
