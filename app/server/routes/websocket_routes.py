"""
WebSocket route for real-time game state updates.

A single WebSocket endpoint per game session.  Multiple clients can
connect to the same session and receive broadcasts of state updates,
AI actions, and RAG referee answers.

Routes:
    WS /ws/{session_id} → Persistent connection for push-based updates
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket

if TYPE_CHECKING:
    from app.server.handlers.websocket_handler import WebSocketHandler

router = APIRouter()

# Late-binding DI: handler is assigned by main.py after construction
handler: WebSocketHandler = None  # type: ignore[assignment]


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Establish a WebSocket connection for real-time game updates."""
    await handler.handle_connection(websocket, session_id)
