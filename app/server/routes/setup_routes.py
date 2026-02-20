"""
Setup phase routes for piece placement.

During the setup phase, players place their 5 pieces on their half
of the board before gameplay begins.

Routes:
    POST   /api/game/{id}/setup/place    → Place a named piece
    DELETE /api/game/{id}/setup/{y}/{x}  → Remove a placed piece
    POST   /api/game/{id}/setup/confirm  → Confirm placement for current team
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.server.models import SetupPlaceRequest

if TYPE_CHECKING:
    from app.server.handlers.setup_handler import SetupHandler

router = APIRouter(prefix="/api/game", tags=["setup"])

# Late-binding DI: handler is assigned by main.py after construction
handler: SetupHandler = None  # type: ignore[assignment]


@router.post("/{session_id}/setup/place")
async def setup_place(session_id: str, body: SetupPlaceRequest):
    """Place a named piece at the specified cell during setup."""
    return await handler.place_piece(session_id, body.name, body.y, body.x)


@router.delete("/{session_id}/setup/{y}/{x}")
async def setup_remove(session_id: str, y: int, x: int):
    """Remove a previously placed piece (undo) during setup."""
    return await handler.remove_piece(session_id, y, x)


@router.post("/{session_id}/setup/confirm")
async def setup_confirm(session_id: str):
    """Confirm the current team's placement and advance setup."""
    return await handler.confirm_placement(session_id)
