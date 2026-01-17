"""Tests for game storage functionality."""

import pytest
import os
import tempfile
from pathlib import Path
from app.storage import save_game, load_game, list_saves, delete_save
from app.engine.game_state import GameState


class TestStorage:
    """Tests for storage module."""
    
    def setup_method(self):
        """Set up test environment."""
        # Use a temporary directory for saves during tests
        self.original_saves_dir = None
        self.temp_dir = tempfile.mkdtemp()
        # Note: In a real test, we'd mock the SAVES_DIR constant
        # For now, we'll test with the actual saves directory
    
    def test_save_game(self):
        """Test saving a game."""
        game = GameState.create_initial_game()
        game.moves_made = 1
        
        save_path = save_game(game, 'test_save')
        assert os.path.exists(save_path)
        assert save_path.endswith('.json')
        
        # Clean up
        delete_save('test_save')
    
    def test_load_game(self):
        """Test loading a game."""
        game = GameState.create_initial_game()
        game.moves_made = 2
        game.current_player = 'brown'
        
        save_game(game, 'test_load')
        
        loaded = load_game('test_load')
        assert loaded.moves_made == 2
        assert loaded.current_player == 'brown'
        
        # Clean up
        delete_save('test_load')
    
    def test_load_nonexistent_game(self):
        """Test loading a non-existent game raises error."""
        with pytest.raises(FileNotFoundError):
            load_game('nonexistent_game_12345')
    
    def test_list_saves(self):
        """Test listing saved games."""
        # Create a few saves
        game1 = GameState.create_initial_game()
        game2 = GameState.create_initial_game()
        
        save_game(game1, 'test_list1')
        save_game(game2, 'test_list2')
        
        saves = list_saves()
        assert 'test_list1' in saves
        assert 'test_list2' in saves
        
        # Clean up
        delete_save('test_list1')
        delete_save('test_list2')
    
    def test_delete_save(self):
        """Test deleting a save."""
        game = GameState.create_initial_game()
        save_game(game, 'test_delete')
        
        deleted = delete_save('test_delete')
        assert deleted is True
        
        # Verify it's gone
        saves = list_saves()
        assert 'test_delete' not in saves
    
    def test_delete_nonexistent_save(self):
        """Test deleting non-existent save returns False."""
        deleted = delete_save('nonexistent_delete_12345')
        assert deleted is False
    
    def test_save_invalid_game_state(self):
        """Test saving invalid game state raises error."""
        with pytest.raises(ValueError, match="GameState instance"):
            save_game("not a game state", 'test_invalid')
    
    def test_save_load_round_trip(self):
        """Test complete save/load cycle preserves all data."""
        game = GameState.create_custom_game()
        
        # Place some pieces
        game.place_piece(4, 0, 'white', 'square')
        game.place_piece(4, 1, 'white', 'square')
        game.place_piece(5, 0, 'brown', 'square')
        
        save_game(game, 'test_round_trip')
        loaded = load_game('test_round_trip')
        
        # Verify all state
        assert loaded.setup_mode == game.setup_mode
        assert loaded.current_player == game.current_player
        assert loaded.moves_made == game.moves_made
        
        # Verify pieces
        assert loaded.board.get_piece(4, 0) is not None
        assert loaded.board.get_piece(4, 1) is not None
        assert loaded.board.get_piece(5, 0) is not None
        
        # Clean up
        delete_save('test_round_trip')
    
    def test_save_filename_without_extension(self):
        """Test that .json extension is added automatically."""
        game = GameState.create_initial_game()
        save_path = save_game(game, 'test_no_ext')
        assert save_path.endswith('.json')
        
        # Should be able to load without extension too
        loaded = load_game('test_no_ext')
        assert loaded is not None
        
        # Clean up
        delete_save('test_no_ext')
