"""Game storage functions for saving and loading game states to/from JSON files."""

import os
import json
from pathlib import Path
from app.engine.game_state import GameState


# Directory where save files are stored
SAVES_DIR = Path(__file__).parent.parent.parent / 'saves'


def _ensure_saves_dir():
    """Ensure the saves directory exists, create it if it doesn't."""
    SAVES_DIR.mkdir(exist_ok=True)


def _get_save_path(filename):
    """Get the full path to a save file, ensuring .json extension."""
    _ensure_saves_dir()
    if not filename.endswith('.json'):
        filename += '.json'
    return SAVES_DIR / filename


def save_game(game_state, filename):
    """
    Save a game state to a JSON file in the saves directory.
    
    Args:
        game_state: GameState object to save
        filename: Name of the save file (will add .json if not present)
    
    Returns:
        str: Full path to the saved file
    
    Raises:
        ValueError: If game_state is not a GameState instance
        IOError: If file cannot be written
    """
    if not isinstance(game_state, GameState):
        raise ValueError("game_state must be a GameState instance")
    
    save_path = _get_save_path(filename)
    
    try:
        game_state.save_to_file(str(save_path))
        return str(save_path)
    except Exception as e:
        raise IOError(f"Failed to save game to {save_path}: {e}")


def load_game(filename):
    """
    Load a game state from a JSON file in the saves directory.
    
    Args:
        filename: Name of the save file (will add .json if not present)
    
    Returns:
        GameState: The loaded game state
    
    Raises:
        FileNotFoundError: If the save file doesn't exist
        ValueError: If the file contains invalid game data
        IOError: If file cannot be read
    """
    save_path = _get_save_path(filename)
    
    if not save_path.exists():
        raise FileNotFoundError(f"Save file not found: {save_path}")
    
    try:
        return GameState.load_from_file(str(save_path))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in save file {save_path}: {e}")
    except Exception as e:
        raise IOError(f"Failed to load game from {save_path}: {e}")


def list_saves():
    """
    Get a list of all available save files.
    
    Returns:
        list: List of save file names (without .json extension)
    """
    _ensure_saves_dir()
    
    save_files = []
    for file_path in SAVES_DIR.glob('*.json'):
        # Return filename without .json extension
        save_files.append(file_path.stem)
    
    return sorted(save_files)


def delete_save(filename):
    """
    Delete a save file.
    
    Args:
        filename: Name of the save file to delete (will add .json if not present)
    
    Returns:
        bool: True if file was deleted, False if it didn't exist
    
    Raises:
        IOError: If file cannot be deleted
    """
    save_path = _get_save_path(filename)
    
    if not save_path.exists():
        return False
    
    try:
        save_path.unlink()
        return True
    except Exception as e:
        raise IOError(f"Failed to delete save file {save_path}: {e}")
