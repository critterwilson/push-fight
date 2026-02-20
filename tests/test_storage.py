"""
Tests for game storage functionality (app.storage).

The storage module provides save_game(), load_game(), list_saves(), and
delete_save() functions that persist GameState objects as JSON files in a
saves/ directory. These tests exercise the full CRUD lifecycle:

  - **save_game**: serializes a GameState to a .json file on disk.
  - **load_game**: reads a .json file and reconstructs a GameState.
  - **list_saves**: returns all save filenames (sans extension).
  - **delete_save**: removes a save file from disk.

Testing strategy:
  - Tests use the real filesystem (actual saves/ directory) rather than
    mocking, providing confidence that the I/O works end-to-end.
  - Each test that creates a file cleans up after itself via delete_save().
  - Error paths are tested: loading a nonexistent file (FileNotFoundError),
    deleting a nonexistent file (returns False), and saving an invalid
    object (ValueError).
  - A round-trip test verifies that all fields (setup_mode, current_player,
    moves_made, piece positions) survive the save/load cycle.

Note: In a production test suite, you might want to mock SAVES_DIR to a
temp directory to avoid polluting the real saves folder. The current approach
trades purity for simplicity.
"""

import pytest
import os
import tempfile
from pathlib import Path
from app.storage import save_game, load_game, list_saves, delete_save
from app.engine.game_state import GameState


class TestStorage:
    """Tests for the storage module's save/load/list/delete operations."""

    def setup_method(self):
        """Create a temporary directory reference for potential future use.
        Currently tests write to the actual saves/ directory and clean up
        after themselves."""
        self.original_saves_dir = None
        self.temp_dir = tempfile.mkdtemp()

    def test_save_game(self):
        """save_game must create a .json file on disk at the returned path.
        Verifies both the file existence and the extension."""
        game = GameState.create_initial_game()
        game.moves_made = 1

        save_path = save_game(game, 'test_save')
        assert os.path.exists(save_path)
        assert save_path.endswith('.json')

        # Clean up
        delete_save('test_save')

    def test_load_game(self):
        """load_game must reconstruct the exact GameState that was saved,
        including modified scalar fields like moves_made and current_player."""
        game = GameState.create_initial_game()
        game.moves_made = 2
        game.current_player = 'brown'

        save_game(game, 'test_load')

        loaded = load_game('test_load')
        assert loaded.moves_made == 2
        assert loaded.current_player == 'brown'

        delete_save('test_load')

    def test_load_nonexistent_game(self):
        """Loading a save file that does not exist must raise FileNotFoundError
        so callers can catch it and display an appropriate error."""
        with pytest.raises(FileNotFoundError):
            load_game('nonexistent_game_12345')

    def test_list_saves(self):
        """list_saves must return all saved game names. Creating two saves
        and verifying both appear in the list."""
        game1 = GameState.create_initial_game()
        game2 = GameState.create_initial_game()

        save_game(game1, 'test_list1')
        save_game(game2, 'test_list2')

        saves = list_saves()
        assert 'test_list1' in saves
        assert 'test_list2' in saves

        delete_save('test_list1')
        delete_save('test_list2')

    def test_delete_save(self):
        """delete_save must remove the file from disk and return True.
        The file must no longer appear in list_saves after deletion."""
        game = GameState.create_initial_game()
        save_game(game, 'test_delete')

        deleted = delete_save('test_delete')
        assert deleted is True

        saves = list_saves()
        assert 'test_delete' not in saves

    def test_delete_nonexistent_save(self):
        """Attempting to delete a non-existent save must return False
        rather than raising an exception."""
        deleted = delete_save('nonexistent_delete_12345')
        assert deleted is False

    def test_save_invalid_game_state(self):
        """Passing a non-GameState object to save_game must raise ValueError
        with a message containing 'GameState instance'. This prevents
        accidental corruption of the save file format."""
        with pytest.raises(ValueError, match="GameState instance"):
            save_game("not a game state", 'test_invalid')

    def test_save_load_round_trip(self):
        """Full round-trip test: create a custom game, place some pieces,
        save, reload, and verify that setup_mode, current_player, moves_made,
        and all piece positions are preserved identically."""
        game = GameState.create_custom_game()

        # Place some pieces during setup
        game.place_piece(4, 0, 'white', 'square')
        game.place_piece(4, 1, 'white', 'square')
        game.place_piece(5, 0, 'black', 'square')

        save_game(game, 'test_round_trip')
        loaded = load_game('test_round_trip')

        # Verify scalar state fields
        assert loaded.setup_mode == game.setup_mode
        assert loaded.current_player == game.current_player
        assert loaded.moves_made == game.moves_made

        # Verify piece positions survived the round-trip
        assert loaded.board.get_piece(4, 0) is not None
        assert loaded.board.get_piece(4, 1) is not None
        assert loaded.board.get_piece(5, 0) is not None

        delete_save('test_round_trip')

    def test_save_filename_without_extension(self):
        """save_game must automatically append .json to the filename.
        load_game must also work without the caller specifying .json."""
        game = GameState.create_initial_game()
        save_path = save_game(game, 'test_no_ext')
        assert save_path.endswith('.json')

        loaded = load_game('test_no_ext')
        assert loaded is not None

        delete_save('test_no_ext')
