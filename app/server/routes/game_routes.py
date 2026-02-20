"""
Game lifecycle and action routes.

Defines the core REST endpoints for creating games, retrieving state,
executing moves and pushes, and skipping moves.  Each route delegates
to the GameHandler, which is injected via late-binding in main.py.

Routes:
    POST /api/game                    → Create a new game session
    GET  /api/game/{session_id}       → Get current game state
    POST /api/game/{session_id}/move  → Execute a piece move
    POST /api/game/{session_id}/push  → Execute a push
    POST /api/game/{session_id}/skip-moves → Skip to push phase
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.server.models import CreateGameRequest, MoveRequest, PushRequest

if TYPE_CHECKING:
    from app.server.handlers.game_handler import GameHandler

router = APIRouter(prefix="/api/game", tags=["game"])

# Late-binding DI: handler is assigned by main.py after construction
handler: GameHandler = None  # type: ignore[assignment]


@router.post("")
def create_game(body: CreateGameRequest):
    """Create a new game session with the specified mode and difficulty."""
    return handler.create_game(body.mode, body.difficulty, body.player_color)


@router.get("/{session_id}")
def get_game(session_id: str):
    """Retrieve the current state of an existing game session."""
    return handler.get_game(session_id)


@router.post("/{session_id}/move")
async def make_move(session_id: str, body: MoveRequest):
    """Slide a piece from one cell to another."""
    return await handler.make_move(session_id, body.from_pos, body.to_pos)


@router.post("/{session_id}/push")
async def make_push(session_id: str, body: PushRequest):
    """Push with a square piece in a cardinal direction."""
    return await handler.make_push(session_id, body.piece, body.direction)


@router.post("/{session_id}/skip-moves")
async def skip_moves(session_id: str):
    """Skip remaining moves and advance to the push phase."""
    return await handler.skip_moves(session_id)
