"""Integration tests for complete game workflows."""

import pytest
from app.engine.game_state import GameState
from app.storage import save_game, load_game, delete_save


class TestGameWorkflow:
    """Tests for complete game workflows."""
    
    def test_complete_custom_setup_workflow(self):
        """Test complete custom setup workflow."""
        # Create custom game
        game = GameState.create_custom_game()
        assert game.setup_mode is True
        
        # Place white pieces
        for i in range(3):
            success, _ = game.place_piece(4, i, 'white', 'square')
            assert success is True
        for i in range(2):
            success, _ = game.place_piece(3, i, 'white', 'round')
            assert success is True
        
        # Place black pieces
        for i in range(3):
            success, _ = game.place_piece(5, i, 'black', 'square')
            assert success is True
        for i in range(2):
            success, _ = game.place_piece(6, i, 'black', 'round')
            assert success is True

        # Verify placement
        white_status = game.get_placement_status('white')
        brown_status = game.get_placement_status('black')
        assert white_status['squares'] == 3
        assert white_status['rounds'] == 2
        assert brown_status['squares'] == 3
        assert brown_status['rounds'] == 2
        
        # Start game
        success, _ = game.start_game()
        assert success is True
        assert game.setup_mode is False
        assert game.current_player == 'white'
    
    def test_move_and_push_workflow(self):
        """Test move and push workflow."""
        game = GameState.create_initial_game()
        
        # Find a white piece with valid moves
        white_piece_pos = None
        for y in range(10):
            for x in range(4):
                piece = game.board.get_piece(y, x)
                if piece and piece.team == 'white':
                    valid_moves = game.board.get_valid_moves(y, x)
                    if valid_moves:
                        white_piece_pos = (y, x)
                        break
            if white_piece_pos:
                break
        
        if white_piece_pos:
            y, x = white_piece_pos
            valid_moves = game.board.get_valid_moves(y, x)
            dest_y, dest_x = list(valid_moves)[0]
            
            # Move piece
            piece = game.board.get_piece(y, x)
            game.board.pieces[y][x] = None
            game.board.pieces[dest_y][dest_x] = piece
            game.moves_made = 1
            
            # Find a square piece to push
            for py in range(10):
                for px in range(4):
                    push_piece = game.board.get_piece(py, px)
                    if push_piece and push_piece.team == 'white' and push_piece.shape == 'square':
                        # Try to push
                        success = game.perform_push(py, px, (1, 0))
                        # May succeed or fail, but should not crash
                        assert isinstance(success, bool)
                        break
                else:
                    continue
                break
    
    def test_save_load_workflow(self):
        """Test complete save/load workflow."""
        # Create and modify game
        game = GameState.create_initial_game()
        game.moves_made = 2
        game.current_player = 'black'

        # Save
        save_path = save_game(game, 'test_workflow')
        assert save_path is not None

        # Load
        loaded = load_game('test_workflow')
        assert loaded.moves_made == 2
        assert loaded.current_player == 'black'
        
        # Verify board state
        for y in range(10):
            for x in range(4):
                orig_piece = game.board.get_piece(y, x)
                loaded_piece = loaded.board.get_piece(y, x)
                if orig_piece is None:
                    assert loaded_piece is None
                else:
                    assert loaded_piece is not None
                    assert orig_piece.team == loaded_piece.team
                    assert orig_piece.shape == loaded_piece.shape
        
        # Clean up
        delete_save('test_workflow')
    
    def test_setup_save_load_workflow(self):
        """Test saving and loading a game in setup mode."""
        # Create custom game and place pieces
        game = GameState.create_custom_game()
        game.place_piece(4, 0, 'white', 'square')
        game.place_piece(4, 1, 'white', 'square')
        game.place_piece(5, 0, 'black', 'square')
        
        # Save
        save_game(game, 'test_setup_workflow')
        
        # Load
        loaded = load_game('test_setup_workflow')
        assert loaded.setup_mode is True
        assert loaded.board.get_piece(4, 0) is not None
        assert loaded.board.get_piece(4, 1) is not None
        assert loaded.board.get_piece(5, 0) is not None
        
        # Clean up
        delete_save('test_setup_workflow')
    
    def test_turn_switching_workflow(self):
        """Test complete turn switching workflow."""
        game = GameState.create_initial_game()
        assert game.current_player == 'white'
        
        # Complete a turn (simulate push)
        game.push_completed = True
        game.switch_turn()
        assert game.current_player == 'black'
        assert game.moves_made == 0
        assert game.push_completed is False
        
        # Switch again
        game.push_completed = True
        game.switch_turn()
        assert game.current_player == 'white'
