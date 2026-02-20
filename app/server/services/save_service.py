"""
Save/load game state to/from disk as JSON files.

Games are persisted in the ``saves/`` directory.  Each save file is a
JSON serialization of the full GameState (board layout, turn state,
pieces pushed off, etc.).

Save names are user-provided strings (sanitized by the filesystem).
The ``.json`` extension is added/stripped automatically so users see
clean names in the save list.

The saves directory is created on-demand (``os.makedirs``) so the app
works out of the box without manual setup.
"""

from __future__ import annotations
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.server.session import GameSession


class SaveService:
    """File-based game persistence using JSON serialization."""

    _SAVE_DIR = "saves"

    def save_game(self, session: "GameSession", filename: str) -> str:
        """Serialize the current game state to a JSON file.

        Args:
            session:  The active game session to save.
            filename: Base name for the save file (without .json extension).

        Returns:
            The full file path of the saved game.
        """
        os.makedirs(self._SAVE_DIR, exist_ok=True)
        filepath = os.path.join(self._SAVE_DIR, f"{filename}.json")
        session.game.save_to_file(filepath)
        return filepath

    def list_saves(self) -> list[str]:
        """Return a sorted list of save names (without .json extension)."""
        os.makedirs(self._SAVE_DIR, exist_ok=True)
        files = [f[:-5] for f in os.listdir(self._SAVE_DIR) if f.endswith(".json")]
        return sorted(files)

    def load_save(self, session: "GameSession", filename: str) -> None:
        """Load a saved game state into an existing session.

        Replaces the session's GameState entirely with the loaded state.

        Raises:
            FileNotFoundError: If the save file doesn't exist.
        """
        filepath = os.path.join(self._SAVE_DIR, f"{filename}.json")
        if not os.path.exists(filepath):
            raise FileNotFoundError("Save file not found")
        from app.engine.game_state import GameState
        session.game = GameState.load_from_file(filepath)
