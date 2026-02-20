"""
Handler for the RAG referee endpoint.

The RAG (Retrieval-Augmented Generation) referee answers natural-language
questions about the game rules and current board state.  It uses a local
Ollama LLM with ChromaDB vector retrieval over the rules document.

The answer is delivered asynchronously via WebSocket (not in the HTTP
response) because LLM inference can take several seconds.  The HTTP
response returns immediately with a "question submitted" acknowledgment.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from app.server.services.game_service import GameService
    from app.server.services.rag_service import RAGService


class RagHandler:
    """Submits questions to the RAG service for async answering."""

    def __init__(self, game_service: GameService, rag_service: RAGService):
        self.game = game_service
        self.rag = rag_service

    def _get_session(self, session_id: str):
        """Look up a session or raise HTTP 404."""
        try:
            return self.game.get_session_or_raise(session_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Session not found")

    async def ask_referee(self, session_id: str, question: str) -> dict:
        """Submit a question to the RAG referee — answer arrives via WebSocket.

        The question is processed asynchronously: the RAG service formats
        the game state, queries the LLM, and broadcasts the answer as a
        'rag_answer' WebSocket event to the session's subscribers.
        """
        session = self._get_session(session_id)
        await self.rag.ask_question(session_id, session, question)
        return {"status": "question submitted"}
