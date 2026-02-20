"""
Handlers for game save/load/list endpoints.

Provides persistence for game sessions via JSON files on disk.
  - Save: serialize the current GameState to a named file.
  - Load: restore a saved GameState into the current session.
  - List: return all available save file names.

After loading a save, the updated state is broadcast to all WebSocket
subscribers so all connected clients see the restored game.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.server.state_serializer import serialize_state

if TYPE_CHECKING:
    from app.server.services.broadcast_service import BroadcastService
    from app.server.services.game_service import GameService
    from app.server.services.save_service import SaveService


class SaveHandler:
    """Orchestrates save/load operations and broadcasts state after load."""

    def __init__(self, game_service: GameService, save_service: SaveService,
                 broadcast_service: BroadcastService):
        self.game = game_service
        self.save = save_service
        self.broadcast = broadcast_service

    def _get_session(self, session_id: str):
        """Look up a session or raise HTTP 404."""
        try:
            return self.game.get_session_or_raise(session_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Session not found")

    def save_game(self, session_id: str, filename: str) -> dict:
        """Save the current game state to disk under the given filename."""
        session = self._get_session(session_id)
        filepath = self.save.save_game(session, filename)
        return {"saved": filepath}

    def list_saves(self) -> dict:
        """Return a list of all available save file names."""
        return {"saves": self.save.list_saves()}

    async def load_save(self, session_id: str, filename: str) -> dict:
        """Load a saved game into the current session and broadcast the update."""
        session = self._get_session(session_id)
        try:
            self.save.load_save(session, filename)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Save file not found")
        state = serialize_state(session)
        await self.broadcast.broadcast_state_update(session_id, state)
        return {"success": True, "state": state}
