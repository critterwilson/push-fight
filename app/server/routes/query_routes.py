"""
Board query routes for valid moves and push directions.

Read-only endpoints used by the frontend to display move indicators
(blue dots) and push direction arrows on the board.

Routes:
    GET /api/game/{id}/valid-moves/{y}/{x}  → Reachable cells for a piece
    GET /api/game/{id}/valid-pushes/{y}/{x} → Valid push directions for a square piece
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import APIRouter

if TYPE_CHECKING:
    from app.server.handlers.query_handler import QueryHandler

router = APIRouter(prefix="/api/game", tags=["queries"])

# Late-binding DI: handler is assigned by main.py after construction
handler: QueryHandler = None  # type: ignore[assignment]


@router.get("/{session_id}/valid-moves/{y}/{x}")
def valid_moves(session_id: str, y: int, x: int):
    """Return all cells the piece at (y, x) can move to via BFS pathfinding."""
    return handler.valid_moves(session_id, y, x)


@router.get("/{session_id}/valid-pushes/{y}/{x}")
def valid_pushes(session_id: str, y: int, x: int):
    """Return all valid push direction vectors for the square piece at (y, x)."""
    return handler.valid_pushes(session_id, y, x)
