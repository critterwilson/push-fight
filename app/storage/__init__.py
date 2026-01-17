"""Storage module for saving and loading game states."""

from .game_storage import save_game, load_game, list_saves, delete_save

__all__ = ['save_game', 'load_game', 'list_saves', 'delete_save']
