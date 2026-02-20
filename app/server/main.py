"""
Push Fight: BJJ Edition — FastAPI web server.

This is the application entry point that wires together all layers of the
server architecture using a manual dependency-injection pattern:

    Services → Handlers → Routes → FastAPI app

Architecture overview:
  - **Services** contain business logic (game actions, AI, broadcasting).
  - **Handlers** orchestrate service calls and format responses.
  - **Routes** define HTTP/WebSocket endpoints and delegate to handlers.

The late-binding DI pattern (assigning handlers to route modules after import)
avoids circular imports while keeping the wiring explicit and testable.

Run with:
    uv run uvicorn app.server.main:app --reload --port 8000

Endpoints
---------
REST
    GET  /health                            Health check
    POST /api/game                          Create new game session
    GET  /api/game/{id}                     Get current game state
    POST /api/game/{id}/move                Perform a move
    POST /api/game/{id}/push                Perform a push
    POST /api/game/{id}/skip-moves          Skip remaining moves (→ push phase)
    GET  /api/game/{id}/valid-moves/{y}/{x} Valid move destinations for a piece
    GET  /api/game/{id}/valid-pushes/{y}/{x} Valid push directions for a piece
    POST /api/game/{id}/save                Save game to disk
    GET  /api/saves                         List saved games
    POST /api/game/{id}/load/{filename}     Restore a save into this session
    POST /api/game/{id}/ask                 Ask the RAG referee (answer via WS)

WebSocket
    WS   /ws/{id}                           Real-time state updates

    Server → client events (JSON):
        { "event": "state_update", "state": <GameStateResponse> }
        { "event": "ai_action",   "action": <action dict> }
        { "event": "ai_done" }
        { "event": "rag_answer",  "answer": <str> }
        { "event": "error",       "message": <str> }
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.server.session import SessionManager

# ---------------------------------------------------------------------------
# Shared state — single in-memory session store for the process
# ---------------------------------------------------------------------------

sessions = SessionManager()

# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan hook — initializes singletons on startup.

    The RAG AI interface (Ollama + ChromaDB) is eagerly constructed here
    so the first /ask request doesn't pay the cold-start cost.
    """
    from app.rag.ai_interface import AIInterface
    AIInterface()
    yield


app = FastAPI(title="Push Fight API", version="1.0.0", lifespan=lifespan)

# Allow all origins for local development and LAN play
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Dependency injection wiring: Services → Handlers → Routes
#
# 1. Create service instances (stateless business logic).
# 2. Create handler instances, injecting services they depend on.
# 3. Assign handlers to route modules via late-binding module attributes.
# 4. Register route modules as FastAPI routers.
# ---------------------------------------------------------------------------

from app.server.services.broadcast_service import BroadcastService
from app.server.services.game_service import GameService
from app.server.services.setup_service import SetupService
from app.server.services.ai_service import AIService
from app.server.services.save_service import SaveService
from app.server.services.rag_service import RAGService

# Service layer — each service encapsulates a single responsibility
broadcast_svc = BroadcastService(sessions)
game_svc = GameService(sessions)
setup_svc = SetupService()
ai_svc = AIService(sessions, broadcast_svc)
save_svc = SaveService()
rag_svc = RAGService(broadcast_svc)

from app.server.handlers.game_handler import GameHandler
from app.server.handlers.setup_handler import SetupHandler
from app.server.handlers.query_handler import QueryHandler
from app.server.handlers.save_handler import SaveHandler
from app.server.handlers.rag_handler import RagHandler
from app.server.handlers.websocket_handler import WebSocketHandler

# Handler layer — orchestrates services and formats responses
game_hdl = GameHandler(game_svc, broadcast_svc, ai_svc)
setup_hdl = SetupHandler(game_svc, setup_svc, broadcast_svc, ai_svc)
query_hdl = QueryHandler(game_svc)
save_hdl = SaveHandler(game_svc, save_svc, broadcast_svc)
rag_hdl = RagHandler(game_svc, rag_svc)
ws_hdl = WebSocketHandler(sessions)

from app.server.routes import (
    health_routes,
    game_routes,
    setup_routes,
    query_routes,
    save_routes,
    rag_routes,
    websocket_routes,
)

# Late-binding DI: assign handler instances to route modules so they can
# call handler methods without importing them directly (avoids circular deps)
game_routes.handler = game_hdl
setup_routes.handler = setup_hdl
query_routes.handler = query_hdl
save_routes.handler = save_hdl
rag_routes.handler = rag_hdl
websocket_routes.handler = ws_hdl

# Register all route groups on the FastAPI app
app.include_router(health_routes.router)
app.include_router(game_routes.router)
app.include_router(setup_routes.router)
app.include_router(query_routes.router)
app.include_router(save_routes.router)
app.include_router(rag_routes.router)
app.include_router(websocket_routes.router)

# ---------------------------------------------------------------------------
# Static file serving — mounted LAST so API routes take priority
# ---------------------------------------------------------------------------

_BENCHMARK_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "benchmark")
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")

# Serve benchmark dashboard if the directory exists
if os.path.isdir(_BENCHMARK_DIR):
    app.mount("/benchmark", StaticFiles(directory=_BENCHMARK_DIR, html=True), name="benchmark")

# Serve the built React frontend as a static SPA
if os.path.isdir(_STATIC_DIR):
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
