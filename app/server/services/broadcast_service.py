"""
WebSocket broadcast service — sends JSON payloads to all connected clients.

This service is the central hub for real-time communication.  Every
state-mutating action (move, push, setup, save-load) broadcasts the
updated state through this service, ensuring all connected clients
stay synchronized.

Handles dead connections gracefully: if a send fails (e.g. client
disconnected without a clean close), the socket is removed from the
session's subscriber list to prevent repeated failures.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.server.session import SessionManager


class BroadcastService:
    """Sends JSON events to all WebSocket subscribers of a game session."""

    def __init__(self, session_manager: SessionManager):
        self._sessions = session_manager

    async def broadcast(self, session_id: str, payload: dict) -> None:
        """Send a JSON message to every WebSocket connected to this session.

        Silently removes any dead sockets that fail during send.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return

        # Collect dead sockets to avoid modifying list during iteration
        dead: list = []
        for ws in session.websockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        # Clean up disconnected sockets
        for ws in dead:
            session.websockets.remove(ws)

    async def broadcast_state_update(self, session_id: str, state: dict) -> None:
        """Convenience wrapper: broadcast a 'state_update' event with game state."""
        await self.broadcast(session_id, {"event": "state_update", "state": state})
