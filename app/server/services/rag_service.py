"""
RAG referee service — submits questions and delivers answers via WebSocket.

This service bridges the synchronous RAG engine (which runs LLM inference
in a background thread) with the async WebSocket broadcast system.

Flow:
  1. The handler calls ``ask_question()`` with the session and question.
  2. The RAG engine processes the question in a background thread
     (via the AIInterface's thread pool).
  3. When the answer is ready, a callback uses ``loop.call_soon_threadsafe``
     to schedule a broadcast on the event loop.
  4. The answer is delivered to all connected clients as a 'rag_answer'
     WebSocket event.

This async-to-sync bridge is necessary because the Ollama LLM call is
blocking and would otherwise freeze the event loop.
"""

from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.server.services.broadcast_service import BroadcastService
    from app.server.session import GameSession


class RAGService:
    """Submits questions to the RAG engine and broadcasts answers."""

    def __init__(self, broadcast_service: BroadcastService):
        self._broadcast = broadcast_service

    async def ask_question(self, session_id: str, session: "GameSession",
                           question: str) -> None:
        """Submit a question to the RAG engine for async answering.

        The answer will be broadcast to all WebSocket subscribers of
        this session as a 'rag_answer' event once the LLM responds.

        Args:
            session_id: Game session ID for broadcasting the answer.
            session:    The game session (provides current board state).
            question:   The user's natural-language question.
        """
        loop = asyncio.get_running_loop()

        def _callback(answer: str) -> None:
            """Thread-safe callback invoked when the LLM produces an answer."""
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(
                    self._broadcast.broadcast(
                        session_id,
                        {"event": "rag_answer", "answer": answer},
                    )
                )
            )

        from app.rag.ai_interface import AIInterface
        ai = AIInterface()
        ai.ask_question(session.game, question, _callback)
