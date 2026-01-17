"""Tests for game engine components."""

import pytest
from app.engine.pieces import Piece
from app.engine.board import PushFightBoard
from app.engine.game_state import GameState


class TestPiece:
    """Tests for Piece class."""
    
    def test_piece_creation(self):
        """Test creating pieces."""
        white_square = Piece('white', 'square')
        assert white_square.team == 'white'
        assert white_square.shape == 'square'
        assert white_square.is_square is True
        
        brown_round = Piece('brown', 'round')
        assert brown_round.team == 'brown'
        assert brown_round.shape == 'round'
        assert brown_round.is_square is False
    
    def test_piece_serialization(self):
        """Test piece serialization to/from dict."""
        piece = Piece('white', 'square')
        piece_dict = piece.to_dict()
        
        assert piece_dict == {'team': 'white', 'shape': 'square'}
        
        restored = Piece.from_dict(piece_dict)
        assert restored.team == 'white'
        assert restored.shape == 'square'
        assert restored.is_square is True
    
    def test_piece_from_dict_none(self):
        """Test from_dict handles None."""
        assert Piece.from_dict(None) is None


class TestPushFightBoard:
    """Tests for PushFightBoard class."""
    
    def test_board_creation(self):
        """Test board initialization."""
        board = PushFightBoard()
        assert len(board.grid) == 10
        assert len(board.grid[0]) == 4
        assert board.anchor_pos == (None, None)
    
    def test_is_on_board(self):
        """Test board boundary checking."""
        board = PushFightBoard()
        assert board.is_on_board(0, 0) is True
        assert board.is_on_board(9, 3) is True
        assert board.is_on_board(10, 0) is False
        assert board.is_on_board(0, 4) is False
        assert board.is_on_board(-1, 0) is False
    
    def test_is_kill_zone(self):
        """Test kill zone detection."""
        board = PushFightBoard()
        assert board.is_kill_zone(0, 0) is True  # North kill zone
        assert board.is_kill_zone(9, 0) is True  # South kill zone
        assert board.is_kill_zone(4, 0) is False  # Playable space
    
    def test_get_piece(self):
        """Test getting pieces from board."""
        board = PushFightBoard()
        piece = Piece('white', 'square')
        board.pieces[4][0] = piece
        
        assert board.get_piece(4, 0) == piece
        assert board.get_piece(4, 1) is None
        assert board.get_piece(10, 0) == "OUT_OF_BOUNDS"
    
    def test_is_occupied(self):
        """Test occupied space checking."""
        board = PushFightBoard()
        board.pieces[4][0] = Piece('white', 'square')
        
        assert board.is_occupied(4, 0) is True
        assert board.is_occupied(4, 1) is False
        assert board.is_occupied(0, 0) is False  # Kill zone
    
    def test_get_valid_moves(self):
        """Test BFS valid moves calculation."""
        board = PushFightBoard()
        # Place piece at (4, 0)
        board.pieces[4][0] = Piece('white', 'square')
        
        # Get valid moves from (4, 1) - should have many connected spaces
        valid_moves = board.get_valid_moves(4, 1)
        assert isinstance(valid_moves, set)
        assert len(valid_moves) > 0
        # Should not include the starting position
        assert (4, 1) not in valid_moves
    
    def test_get_push_chain(self):
        """Test push chain calculation."""
        board = PushFightBoard()
        # Create a line of pieces
        board.pieces[4][0] = Piece('white', 'square')
        board.pieces[4][1] = Piece('white', 'square')
        board.pieces[4][2] = Piece('brown', 'square')
        
        # Push from (4, 0) to the right
        chain, landing = board.get_push_chain(4, 0, 0, 1)
        assert len(chain) == 3
        assert (4, 0) in chain
        assert (4, 1) in chain
        assert (4, 2) in chain
    
    def test_board_serialization(self):
        """Test board serialization."""
        board = PushFightBoard()
        board.pieces[4][0] = Piece('white', 'square')
        board.anchor_pos = (4, 0)
        
        board_dict = board.to_dict()
        assert 'grid' in board_dict
        assert 'pieces' in board_dict
        assert 'anchor_pos' in board_dict
        
        restored = PushFightBoard.from_dict(board_dict)
        assert restored.grid == board.grid
        assert restored.anchor_pos == (4, 0)
        assert restored.get_piece(4, 0).team == 'white'


class TestGameState:
    """Tests for GameState class."""
    
    def test_game_creation(self):
        """Test creating initial game."""
        game = GameState.create_initial_game()
        assert game.current_player == 'white'
        assert game.moves_made == 0
        assert game.push_completed is False
        assert game.game_over is False
        assert game.setup_mode is False
    
    def test_custom_game_creation(self):
        """Test creating custom game for setup."""
        game = GameState.create_custom_game()
        assert game.setup_mode is True
        assert game.current_player == 'white'
    
    def test_can_move(self):
        """Test move availability checking."""
        game = GameState.create_initial_game()
        assert game.can_move() is True
        
        game.moves_made = 2
        assert game.can_move() is False
        
        game.moves_made = 1
        game.push_completed = True
        assert game.can_move() is False
    
    def test_can_push(self):
        """Test push availability checking."""
        game = GameState.create_initial_game()
        assert game.can_push() is True
        
        game.push_completed = True
        assert game.can_push() is False
    
    def test_switch_turn(self):
        """Test turn switching."""
        game = GameState.create_initial_game()
        game.push_completed = True
        
        game.switch_turn()
        assert game.current_player == 'brown'
        assert game.moves_made == 0
        assert game.push_completed is False
    
    def test_switch_turn_without_push(self):
        """Test that switching turn without push raises error."""
        game = GameState.create_initial_game()
        with pytest.raises(ValueError, match="You must push"):
            game.switch_turn()
    
    def test_place_piece(self):
        """Test placing pieces during setup."""
        game = GameState.create_custom_game()
        
        # Place white piece on white side
        success, msg = game.place_piece(4, 0, 'white', 'square')
        assert success is True
        assert game.board.get_piece(4, 0) is not None
        
        # Try to place on wrong side
        success, msg = game.place_piece(5, 0, 'white', 'square')
        assert success is False
        assert 'not on' in msg.lower()
    
    def test_place_piece_validation(self):
        """Test piece placement validation."""
        game = GameState.create_custom_game()
        
        # Place 3 squares
        for i in range(3):
            game.place_piece(4, i, 'white', 'square')
        
        # Try to place 4th square
        success, msg = game.place_piece(3, 0, 'white', 'square')
        assert success is False
        assert 'maximum' in msg.lower()
    
    def test_remove_piece(self):
        """Test removing pieces during setup."""
        game = GameState.create_custom_game()
        game.place_piece(4, 0, 'white', 'square')
        
        success, msg = game.remove_piece(4, 0)
        assert success is True
        assert game.board.get_piece(4, 0) is None
    
    def test_get_placement_status(self):
        """Test placement status tracking."""
        game = GameState.create_custom_game()
        game.place_piece(4, 0, 'white', 'square')
        game.place_piece(4, 1, 'white', 'square')
        game.place_piece(4, 2, 'white', 'round')
        
        status = game.get_placement_status('white')
        assert status['squares'] == 2
        assert status['rounds'] == 1
        assert status['total'] == 3
    
    def test_can_start_game(self):
        """Test game start validation."""
        game = GameState.create_custom_game()
        
        # Incomplete placement
        can_start, msg = game.can_start_game()
        assert can_start is False
        
        # Complete placement
        for i in range(3):
            game.place_piece(4, i, 'white', 'square')
        for i in range(2):
            game.place_piece(3, i, 'white', 'round')
        for i in range(3):
            game.place_piece(5, i, 'brown', 'square')
        for i in range(2):
            game.place_piece(6, i, 'brown', 'round')
        
        can_start, msg = game.can_start_game()
        assert can_start is True
    
    def test_start_game(self):
        """Test starting game from setup."""
        game = GameState.create_custom_game()
        
        # Complete placement
        for i in range(3):
            game.place_piece(4, i, 'white', 'square')
        for i in range(2):
            game.place_piece(3, i, 'white', 'round')
        for i in range(3):
            game.place_piece(5, i, 'brown', 'square')
        for i in range(2):
            game.place_piece(6, i, 'brown', 'round')
        
        success, msg = game.start_game()
        assert success is True
        assert game.setup_mode is False
        assert game.current_player == 'white'
    
    def test_perform_push(self):
        """Test performing a push."""
        game = GameState.create_initial_game()
        
        # Find a white square piece
        white_square_y, white_square_x = None, None
        for y in range(10):
            for x in range(4):
                piece = game.board.get_piece(y, x)
                if piece and piece.team == 'white' and piece.shape == 'square':
                    white_square_y, white_square_x = y, x
                    break
            if white_square_y is not None:
                break
        
        assert white_square_y is not None
        
        # Try to push down
        success = game.perform_push(white_square_y, white_square_x, (1, 0))
        # May succeed or fail depending on board state, but should not crash
        assert isinstance(success, bool)
    
    def test_has_legal_push(self):
        """Test legal push detection."""
        game = GameState.create_initial_game()
        has_push = game.has_legal_push()
        assert isinstance(has_push, bool)
    
    def test_game_serialization(self):
        """Test game state serialization."""
        game = GameState.create_initial_game()
        game.moves_made = 1
        game.current_player = 'brown'
        
        game_dict = game.to_dict()
        assert 'board' in game_dict
        assert 'current_player' in game_dict
        assert 'setup_mode' in game_dict
        assert game_dict['moves_made'] == 1
        
        restored = GameState.from_dict(game_dict)
        assert restored.current_player == 'brown'
        assert restored.moves_made == 1
        assert restored.setup_mode == game.setup_mode
