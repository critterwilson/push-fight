"""
WebSocket connection lifecycle handler.

Manages the full lifecycle of a WebSocket connection:
  1. Accept the connection.
  2. Validate the session ID (close with 4004 if invalid).
  3. Register the socket in the session's subscriber list.
  4. Send the current game state as the initial payload.
  5. Keep the connection alive until the client disconnects.
  6. Clean up by removing the socket from the subscriber list.

The WebSocket is used as a server → client push channel.  All game
state updates, AI actions, and RAG answers are broadcast to connected
clients via the BroadcastService.  The client sends no meaningful
messages — the receive loop exists only to detect disconnection.

Important: websocket.accept() MUST be called before websocket.close()
in Starlette/FastAPI — otherwise the server sends an HTTP 403 instead
of a proper WebSocket close frame.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect

from app.server.state_serializer import serialize_state

if TYPE_CHECKING:
    from app.server.session import SessionManager


class WebSocketHandler:
    """Manages WebSocket connection lifecycle and session registration."""

    def __init__(self, session_manager: SessionManager):
        self._sessions = session_manager

    async def handle_connection(self, websocket: WebSocket, session_id: str) -> None:
        """Accept a WebSocket, register it, and hold the connection open.

        Sends the current game state immediately upon connection so the
        client has a consistent initial state without needing a separate
        REST call.
        """
        # Must accept before any close or send operations
        await websocket.accept()

        session = self._sessions.get(session_id)
        if session is None:
            await websocket.close(code=4004)
            return

        # Register this socket for broadcast events
        session.websockets.append(websocket)

        # Send initial state snapshot
        await websocket.send_json(
            {"event": "state_update", "state": serialize_state(session)}
        )

        try:
            # Hold connection open — no client messages are expected,
            # but we need the receive loop to detect disconnection
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            # Clean up subscriber list on disconnect
            if websocket in session.websockets:
                session.websockets.remove(websocket)
