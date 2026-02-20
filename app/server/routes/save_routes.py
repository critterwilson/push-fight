"""
Save, load, and list-saves routes for game persistence.

Provides file-based game state persistence via JSON.  Saves are stored
in the ``saves/`` directory with user-provided filenames.

Routes:
    POST /api/game/{id}/save             → Save current state to disk
    GET  /api/saves                      → List all available save files
    POST /api/game/{id}/load/{filename}  → Restore a save into this session
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import APIRouter

if TYPE_CHECKING:
    from app.server.handlers.save_handler import SaveHandler

router = APIRouter(tags=["saves"])

# Late-binding DI: handler is assigned by main.py after construction
handler: SaveHandler = None  # type: ignore[assignment]


@router.post("/api/game/{session_id}/save")
def save_game(session_id: str, filename: str = "game"):
    """Save the current game state to a named file on disk."""
    return handler.save_game(session_id, filename)


@router.get("/api/saves")
def list_saves():
    """Return a list of all available saved game filenames."""
    return handler.list_saves()


@router.post("/api/game/{session_id}/load/{filename}")
async def load_save(session_id: str, filename: str):
    """Load a previously saved game into the current session."""
    return await handler.load_save(session_id, filename)
