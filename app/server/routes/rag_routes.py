"""
RAG referee route for rules questions.

Provides a single endpoint for asking the AI referee questions about
the game rules and current board state.  Answers are delivered
asynchronously via WebSocket (not in the HTTP response).

Routes:
    POST /api/game/{id}/ask → Submit a question to the RAG referee
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.server.models import AskRequest

if TYPE_CHECKING:
    from app.server.handlers.rag_handler import RagHandler

router = APIRouter(prefix="/api/game", tags=["rag"])

# Late-binding DI: handler is assigned by main.py after construction
handler: RagHandler = None  # type: ignore[assignment]


@router.post("/{session_id}/ask")
async def ask_referee(session_id: str, body: AskRequest):
    """Submit a rules question — the answer is pushed via WebSocket."""
    return await handler.ask_referee(session_id, body.question)
