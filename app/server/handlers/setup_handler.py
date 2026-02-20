"""
Handlers for the setup phase endpoints.

During setup, each player places their 5 pieces (3 square + 2 round)
on their half of the board.  This handler manages:
  - Placing a named piece at a cell
  - Removing a piece (undo a placement)
  - Confirming placement (transition from setup to active play)

After each mutation, the updated state is broadcast to all WebSocket
subscribers.  When both teams have confirmed, gameplay begins — and if
it's the AI's turn, the AI turn is triggered automatically.
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
    from app.server.services.setup_service import SetupService


class SetupHandler:
    """Orchestrates setup-phase service calls and WebSocket broadcasts."""

    def __init__(self, game_service: GameService, setup_service: SetupService,
                 broadcast_service: BroadcastService, ai_service: AIService):
        self.game_svc = game_service
        self.setup = setup_service
        self.broadcast = broadcast_service
        self.ai = ai_service

    def _get_session(self, session_id: str):
        """Look up a session or raise HTTP 404."""
        try:
            return self.game_svc.get_session_or_raise(session_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Session not found")

    async def place_piece(self, session_id: str, name: str, y: int, x: int) -> dict:
        """Place a named piece at (y, x) during setup and broadcast."""
        session = self._get_session(session_id)
        try:
            self.setup.place_piece(session, name, y, x)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        state = serialize_state(session)
        await self.broadcast.broadcast_state_update(session_id, state)
        return {"success": True, "state": state}

    async def remove_piece(self, session_id: str, y: int, x: int) -> dict:
        """Remove a placed piece at (y, x) and broadcast the update."""
        session = self._get_session(session_id)
        try:
            self.setup.remove_piece(session, y, x)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        state = serialize_state(session)
        await self.broadcast.broadcast_state_update(session_id, state)
        return {"success": True, "state": state}

    async def confirm_placement(self, session_id: str) -> dict:
        """Confirm a team's placement — transitions to play when both teams are ready.

        If the game transitions to active play and it's the AI's turn,
        spawns an async task for the AI to take its first turn.
        """
        session = self._get_session(session_id)
        try:
            self.setup.confirm_placement(session)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        state = serialize_state(session)
        await self.broadcast.broadcast_state_update(session_id, state)
        # If setup is complete and it's the AI's turn, start AI play
        if state.get("isAiTurn"):
            asyncio.create_task(self.ai.run_ai_turn(session_id))
        return {"success": True, "state": state}
