"""
Singleton async interface between the UI layer and the RAG referee engine.

The RAG engine (Ollama LLM + ChromaDB vector store) takes several seconds to
initialize.  This module wraps it in a thread-safe singleton so that:

  1. Engine loading happens on a background daemon thread at import time,
     keeping the UI responsive during startup.
  2. Each question is dispatched on its own daemon thread, and the answer
     is delivered via a caller-supplied callback — no blocking the main loop.

Usage (from PyGame or any synchronous UI)::

    ai = AIInterface()           # idempotent singleton
    ai.ask_question(game, "Can I push my own piece off?", on_answer)

The ``callback`` will be invoked **from a background thread**, so the UI
must drain answers through a thread-safe mechanism (e.g. ``queue.Queue``).
"""

import threading
from app.rag.rag_engine import PushFightRAG
from app.rag.state_formatter import format_game_state


class AIInterface:
    """
    Singleton interface for the UI to interact with the RAG engine asynchronously.

    Ensures the UI main loop is never blocked by heavy LLM operations.
    Uses the classic ``__new__`` singleton pattern with an ``_initialized``
    guard so that ``__init__`` only runs once even if the constructor is
    called multiple times.

    Attributes:
        rag_engine (PushFightRAG | None): The underlying LangChain RAG pipeline.
        is_ready (bool): True once the engine has finished loading.
        loading_error (str | None): Error message if engine init failed.
    """

    _instance = None

    def __new__(cls):
        """Return the existing singleton instance, or create one."""
        if cls._instance is None:
            cls._instance = super(AIInterface, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """One-time setup: kick off engine loading on a daemon thread."""
        if self._initialized:
            return

        self.rag_engine = None
        self.is_ready = False
        self.loading_error = None
        self._initialized = True

        # Start loading in a separate thread to avoid blocking UI startup
        self.load_thread = threading.Thread(target=self._load_engine, daemon=True)
        self.load_thread.start()

    def _load_engine(self):
        """Background task: instantiate the heavy RAG pipeline (Ollama + Chroma)."""
        try:
            self.rag_engine = PushFightRAG()
            self.is_ready = True
        except Exception as e:
            self.loading_error = str(e)
            print(f"Error loading AI Engine: {e}")

    def ask_question(self, game_state, question, callback):
        """
        Submit a rules question to the AI referee asynchronously.

        The current board state is serialised to text via
        :func:`format_game_state`, then passed — along with the question —
        to the RAG chain.  The answer string is delivered to *callback*
        from a background thread.

        Args:
            game_state (GameState): The live game state object.
            question (str): The user's natural-language question.
            callback (Callable[[str], None]):
                Invoked with the answer text (or an error message).
                **Called from a background thread** — the caller must
                handle thread safety (e.g. enqueue the result).
        """
        if not self.is_ready:
            if self.loading_error:
                callback(f"System Error: AI failed to initialize. {self.loading_error}")
            else:
                callback("System: AI is warming up... please try again in a moment.")
            return

        def _query_task():
            """Closure executed on a daemon thread to run the RAG chain."""
            try:
                # Convert the GameState object into a plain-text summary for the LLM
                context = format_game_state(game_state)
                answer = self.rag_engine.ask(question, context)
                callback(answer)
            except Exception as e:
                callback(f"System Error: Failed to get answer. {e}")

        # Run query in background thread so the UI stays responsive
        query_thread = threading.Thread(target=_query_task, daemon=True)
        query_thread.start()