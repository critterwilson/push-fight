"""Comprehensive tests for game engine components."""

import pytest
from app.engine.pieces import Piece
from app.engine.board import PushFightBoard
from app.engine.game_state import GameState


# ============================================================
# Piece Tests
# ============================================================

class TestPiece:
    def test_piece_creation(self):
        ws = Piece('white', 'square')
        assert ws.team == 'white'
        assert ws.shape == 'square'
        assert ws.is_square is True

        br = Piece('black', 'round')
        assert br.team == 'black'
        assert br.shape == 'round'
        assert br.is_square is False

    def test_piece_repr(self):
        assert repr(Piece('white', 'square')) == 'WS'
        assert repr(Piece('black', 'round')) == 'BR'

    def test_piece_serialization_roundtrip(self):
        piece = Piece('black', 'square')
        restored = Piece.from_dict(piece.to_dict())
        assert restored.team == 'black'
        assert restored.shape == 'square'
        assert restored.is_square is True

    def test_piece_from_dict_none(self):
        assert Piece.from_dict(None) is None

    # ------------------------------------------------------------------
    # name field (added for voice-control feature)
    # ------------------------------------------------------------------

    def test_piece_name_defaults_to_none(self):
        piece = Piece('white', 'square')
        assert piece.name is None

    def test_piece_name_stored(self):
        piece = Piece('white', 'square', name='sleeve')
        assert piece.name == 'sleeve'

    def test_piece_serialization_includes_name(self):
        piece = Piece('white', 'square', name='lapel')
        d = piece.to_dict()
        assert 'name' in d
        assert d['name'] == 'lapel'

    def test_piece_name_roundtrip(self):
        piece = Piece('black', 'round', name='neck')
        restored = Piece.from_dict(piece.to_dict())
        assert restored.name == 'neck'

    def test_piece_from_dict_missing_name_is_backward_compatible(self):
        """Pieces saved before the name field was added should load without error."""
        old_data = {'team': 'white', 'shape': 'square'}  # no 'name' key
        restored = Piece.from_dict(old_data)
        assert restored.name is None


# ============================================================
# Board Tests
# ============================================================

class TestBoard:
    def test_board_dimensions(self):
        board = PushFightBoard()
        assert len(board.grid) == 10
        assert all(len(row) == 4 for row in board.grid)
        assert len(board.pieces) == 10
        assert all(len(row) == 4 for row in board.pieces)

    def test_kill_zones(self):
        """Row 0 and row 9 are entirely kill zones. Edges of rows 1,2,7,8 are also kill zones."""
        board = PushFightBoard()
        # Full kill zone rows
        for x in range(4):
            assert board.grid[0][x] == -1, f"(0,{x}) should be kill zone"
            assert board.grid[9][x] == -1, f"(9,{x}) should be kill zone"

        # Partial kill zones
        assert board.grid[1][0] == -1
        assert board.grid[1][3] == -1
        assert board.grid[2][3] == -1
        assert board.grid[7][0] == -1
        assert board.grid[8][0] == -1
        assert board.grid[8][3] == -1

    def test_playable_spaces(self):
        """Rows 3-6 are fully playable. Center of rows 1,2,7,8 are playable."""
        board = PushFightBoard()
        for y in range(3, 7):
            for x in range(4):
                assert board.grid[y][x] == 0, f"({y},{x}) should be playable"

        # Partial playable
        assert board.grid[1][1] == 0
        assert board.grid[1][2] == 0
        assert board.grid[2][0] == 0
        assert board.grid[2][1] == 0
        assert board.grid[2][2] == 0

    def test_is_on_board_boundaries(self):
        board = PushFightBoard()
        # Valid positions
        assert board.is_on_board(0, 0) is True
        assert board.is_on_board(9, 3) is True
        # Out of bounds (side rails)
        assert board.is_on_board(-1, 0) is False
        assert board.is_on_board(10, 0) is False
        assert board.is_on_board(0, -1) is False
        assert board.is_on_board(0, 4) is False

    def test_is_kill_zone(self):
        board = PushFightBoard()
        assert board.is_kill_zone(0, 0) is True
        assert board.is_kill_zone(9, 3) is True
        assert board.is_kill_zone(4, 2) is False
        # Out of bounds is NOT a kill zone (it's a side rail)
        assert board.is_kill_zone(10, 0) is False

    def test_get_piece_out_of_bounds(self):
        board = PushFightBoard()
        assert board.get_piece(10, 0) == "OUT_OF_BOUNDS"
        assert board.get_piece(-1, 0) == "OUT_OF_BOUNDS"

    def test_is_occupied(self):
        board = PushFightBoard()
        board.pieces[4][0] = Piece('white', 'square')
        assert board.is_occupied(4, 0) is True
        assert board.is_occupied(4, 1) is False
        # Out of bounds is not occupied
        assert board.is_occupied(10, 0) is False

    def test_get_valid_moves_empty_board(self):
        """On an empty board, a piece should reach all connected playable squares."""
        board = PushFightBoard()
        board.pieces[5][2] = Piece('white', 'square')
        moves = board.get_valid_moves(5, 2)
        # Should not include starting position
        assert (5, 2) not in moves
        # Count total playable spaces: let's verify a few are reachable
        assert (4, 0) in moves
        assert (3, 1) in moves
        assert (6, 1) in moves
        # Kill zones should NOT be reachable
        assert (0, 0) not in moves
        assert (9, 0) not in moves

    def test_get_valid_moves_blocked_by_pieces(self):
        """Pieces block BFS movement."""
        board = PushFightBoard()
        # Place piece at (5,0) and block it with pieces on all sides
        board.pieces[5][0] = Piece('white', 'square')
        board.pieces[4][0] = Piece('black', 'round')
        board.pieces[5][1] = Piece('black', 'round')
        board.pieces[6][0] = Piece('black', 'round')
        moves = board.get_valid_moves(5, 0)
        # Completely surrounded - no moves
        assert len(moves) == 0

    def test_get_valid_moves_partial_blocking(self):
        """Pieces block paths but not all directions."""
        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        # Block right
        board.pieces[5][2] = Piece('black', 'square')
        moves = board.get_valid_moves(5, 1)
        # Can still move up, down, left
        assert (4, 1) in moves
        assert (6, 1) in moves
        assert (5, 0) in moves
        # Cannot reach through (5,2)
        assert (5, 2) not in moves

    def test_get_push_chain_single_piece(self):
        """Pushing a single piece with no others in the line."""
        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        chain, landing = board.get_push_chain(5, 1, 1, 0)  # push down
        assert chain == [(5, 1)]
        assert landing == (6, 1)

    def test_get_push_chain_multiple_pieces(self):
        """Chain of multiple pieces."""
        board = PushFightBoard()
        board.pieces[4][1] = Piece('white', 'square')
        board.pieces[5][1] = Piece('black', 'square')
        board.pieces[6][1] = Piece('black', 'round')
        chain, landing = board.get_push_chain(4, 1, 1, 0)  # push down
        assert len(chain) == 3
        assert chain == [(4, 1), (5, 1), (6, 1)]
        assert landing == (7, 1)

    def test_get_push_chain_to_edge(self):
        """Chain that would push last piece off the board."""
        board = PushFightBoard()
        board.pieces[8][2] = Piece('white', 'square')
        chain, landing = board.get_push_chain(8, 2, 1, 0)  # push down
        assert chain == [(8, 2)]
        assert landing == (9, 2)  # Kill zone

    def test_get_push_chain_side_rail(self):
        """Chain going off the side rail (out of 10x4 array)."""
        board = PushFightBoard()
        board.pieces[4][3] = Piece('white', 'square')
        chain, landing = board.get_push_chain(4, 3, 0, 1)  # push right
        assert chain == [(4, 3)]
        assert landing == (4, 4)  # Out of bounds - side rail

    def test_board_serialization_roundtrip(self):
        board = PushFightBoard()
        board.pieces[4][0] = Piece('white', 'square')
        board.pieces[5][2] = Piece('black', 'round')
        board.anchor_pos = (4, 1)

        restored = PushFightBoard.from_dict(board.to_dict())
        assert restored.grid == board.grid
        assert restored.anchor_pos == (4, 1)
        assert restored.get_piece(4, 0).team == 'white'
        assert restored.get_piece(5, 2).shape == 'round'
        assert restored.get_piece(3, 0) is None


# ============================================================
# GameState Tests - Turn Flow
# ============================================================

class TestGameStateTurnFlow:
    def test_initial_state(self):
        game = GameState.create_initial_game()
        assert game.current_player == 'white'
        assert game.moves_made == 0
        assert game.push_completed is False
        assert game.game_over is False
        assert game.winner is None
        assert game.setup_mode is False

    def test_can_move_initial(self):
        game = GameState.create_initial_game()
        assert game.can_move() is True
        assert game.can_push() is True

    def test_can_move_after_two_moves(self):
        game = GameState.create_initial_game()
        game.moves_made = 2
        assert game.can_move() is False
        assert game.can_push() is True  # Still need to push

    def test_can_move_after_push(self):
        game = GameState.create_initial_game()
        game.push_completed = True
        assert game.can_move() is False
        assert game.can_push() is False

    def test_switch_turn(self):
        game = GameState.create_initial_game()
        game.push_completed = True
        game.moves_made = 1
        game.switch_turn()
        assert game.current_player == 'black'
        assert game.moves_made == 0
        assert game.push_completed is False

    def test_switch_turn_back_to_white(self):
        game = GameState.create_initial_game()
        game.push_completed = True
        game.switch_turn()
        assert game.current_player == 'black'
        game.push_completed = True
        game.switch_turn()
        assert game.current_player == 'white'

    def test_switch_turn_requires_push(self):
        game = GameState.create_initial_game()
        with pytest.raises(ValueError):
            game.switch_turn()

    def test_piece_counts_initial(self):
        game = GameState.create_initial_game()
        assert game.count_square_pieces('white') == 3
        assert game.count_round_pieces('white') == 2
        assert game.count_square_pieces('black') == 3
        assert game.count_round_pieces('black') == 2
        assert game.count_pieces('white') == 5
        assert game.count_pieces('black') == 5


# ============================================================
# GameState Tests - Movement (BFS sliding)
# ============================================================

class TestGameStateMovement:
    def test_white_piece_can_reach_empty_space(self):
        """In initial position, white pieces should have valid moves."""
        game = GameState.create_initial_game()
        # White round at (3,1) - should be able to move to empty spaces
        moves = game.board.get_valid_moves(3, 1)
        assert len(moves) > 0
        # Should reach (3,0) which is empty and adjacent
        assert (3, 0) in moves

    def test_piece_cannot_move_through_pieces(self):
        """Verify BFS doesn't jump over pieces."""
        game = GameState.create_initial_game()
        # White round at (3,1). Row 4 is full of white pieces blocking south.
        # Row 5 is full of black pieces. (3,1) should not reach row 5+.
        moves = game.board.get_valid_moves(3, 1)
        for y, x in moves:
            # Should only reach positions north of the piece wall
            piece_at_dest = game.board.get_piece(y, x)
            assert piece_at_dest is None, f"BFS reached occupied ({y},{x})"

    def test_no_diagonal_movement(self):
        """BFS should only use orthogonal directions."""
        board = PushFightBoard()
        board.pieces[5][0] = Piece('white', 'square')
        # Block orthogonal paths
        board.pieces[4][0] = Piece('black', 'round')
        board.pieces[5][1] = Piece('black', 'round')
        board.pieces[6][0] = Piece('black', 'round')
        moves = board.get_valid_moves(5, 0)
        # Completely blocked orthogonally - even (4,1) diagonal shouldn't be reachable
        assert (4, 1) not in moves
        assert len(moves) == 0


# ============================================================
# GameState Tests - Push Mechanics
# ============================================================

class TestPushMechanics:
    def test_push_requires_square_piece(self):
        """Only square pieces can push."""
        game = GameState.create_initial_game()
        # White round piece at (4,3) - cannot push
        result = game.perform_push(4, 3, (1, 0))
        assert result is False

    def test_push_requires_own_piece(self):
        """Can only push with own pieces."""
        game = GameState.create_initial_game()
        # Black square at (5,0) - white's turn, should fail
        result = game.perform_push(5, 0, (1, 0))
        assert result is False

    def test_push_empty_space(self):
        """Cannot push from an empty space."""
        game = GameState.create_initial_game()
        result = game.perform_push(3, 0, (1, 0))
        assert result is False

    def test_push_blocked_by_side_rail(self):
        """Push into side rail (off 10x4 array) should fail silently."""
        game = GameState.create_initial_game()
        # White square at (4,0) - push left goes off board
        result = game.perform_push(4, 0, (0, -1))
        assert result is False
        # Piece should still be there
        assert game.board.get_piece(4, 0) is not None

    def test_push_single_piece_into_empty(self):
        """Push a single piece into empty space."""
        game = GameState.create_initial_game()
        # Move some pieces to create space. Let's use a simpler setup.
        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        game = GameState(board)

        result = game.perform_push(5, 1, (1, 0))  # Push down
        assert result is True
        assert game.push_completed is True
        # Piece should have moved
        assert game.board.get_piece(5, 1) is None
        assert game.board.get_piece(6, 1) is not None
        assert game.board.get_piece(6, 1).team == 'white'

    def test_push_chain_into_empty(self):
        """Push a chain of pieces into empty space."""
        board = PushFightBoard()
        board.pieces[4][1] = Piece('white', 'square')
        board.pieces[5][1] = Piece('black', 'square')
        game = GameState(board)

        result = game.perform_push(4, 1, (1, 0))  # Push down
        assert result is True
        # White square moved from (4,1) to (5,1)
        assert game.board.get_piece(4, 1) is None
        assert game.board.get_piece(5, 1).team == 'white'
        # Black square moved from (5,1) to (6,1)
        assert game.board.get_piece(6, 1).team == 'black'

    def test_push_into_kill_zone_removes_piece(self):
        """Pushing a piece into a kill zone removes it from the board."""
        board = PushFightBoard()
        board.pieces[8][1] = Piece('white', 'square')
        board.pieces[8][2] = Piece('black', 'round')
        game = GameState(board)

        # Push (8,1) right -> white moves to (8,2), black pushed to (8,3) which is kill zone
        result = game.perform_push(8, 1, (0, 1))
        assert result is True
        # Black round pushed into kill zone (8,3) - removed
        assert game.board.get_piece(8, 3) is None  # kill zone, piece removed
        assert game.pieces_pushed_off['black']['rounds'] == 1

    def test_push_into_kill_zone_triggers_win(self):
        """Pushing a round piece off triggers immediate win."""
        board = PushFightBoard()
        board.pieces[8][1] = Piece('white', 'square')
        board.pieces[8][2] = Piece('black', 'round')
        game = GameState(board)

        result = game.perform_push(8, 1, (0, 1))
        assert result is True
        assert game.game_over is True
        assert game.winner == 'white'  # Black lost a round piece

    def test_two_squares_off_loses(self):
        """Losing 2 square pieces should trigger loss."""
        board = PushFightBoard()
        game = GameState(board)
        # Manually set up state: black already lost 1 square
        game.pieces_pushed_off['black']['squares'] = 1

        # Now push another black square off
        board.pieces[8][1] = Piece('white', 'square')
        board.pieces[8][2] = Piece('black', 'square')

        result = game.perform_push(8, 1, (0, 1))
        assert result is True
        assert game.game_over is True
        assert game.winner == 'white'

    def test_one_round_off_loses(self):
        """Losing 1 round piece should trigger loss."""
        board = PushFightBoard()
        # Place white square that can push black round into kill zone
        # Row 9 is all kill zone. Push from row 8 down.
        board.pieces[7][1] = Piece('white', 'square')
        board.pieces[8][1] = Piece('black', 'round')
        game = GameState(board)

        result = game.perform_push(7, 1, (1, 0))  # Push down
        assert result is True
        assert game.game_over is True
        assert game.winner == 'white'

    def test_push_sets_anchor(self):
        """After a push, anchor is placed at pusher's new position."""
        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        game = GameState(board)

        game.perform_push(5, 1, (1, 0))  # Push down
        # Pusher moved from (5,1) to (6,1), so anchor should be at (6,1)
        assert game.board.anchor_pos == (6, 1)

    def test_anchor_blocks_push_chain(self):
        """Anchor in a push chain blocks the entire push — nothing moves."""
        board = PushFightBoard()
        board.pieces[4][1] = Piece('white', 'square')
        board.pieces[5][1] = Piece('black', 'square')
        board.pieces[6][1] = Piece('black', 'round')
        # Place anchor at (5,1) - the middle piece
        board.anchor_pos = (5, 1)
        game = GameState(board)

        result = game.perform_push(4, 1, (1, 0))  # Push down
        # Anchor at (5,1) blocks the entire chain — no pieces move
        assert result is True  # Push still counts as an action

        # (4,1) should still have white square (didn't move)
        assert game.board.get_piece(4, 1) is not None
        assert game.board.get_piece(4, 1).team == 'white'
        # (5,1) should still have black square (anchored)
        assert game.board.get_piece(5, 1) is not None
        assert game.board.get_piece(5, 1).team == 'black'
        # (6,1) should still have black round (blocked by anchor)
        assert game.board.get_piece(6, 1) is not None
        assert game.board.get_piece(6, 1).shape == 'round'

    def test_push_sets_push_completed(self):
        """A successful push sets push_completed to True."""
        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        game = GameState(board)

        assert game.push_completed is False
        game.perform_push(5, 1, (1, 0))
        assert game.push_completed is True

    def test_failed_push_does_not_set_push_completed(self):
        """A failed push should not set push_completed."""
        game = GameState.create_initial_game()
        # Push into side rail
        game.perform_push(4, 0, (0, -1))
        assert game.push_completed is False

    def test_push_up_toward_kill_zone(self):
        """Push pieces upward into northern kill zone."""
        board = PushFightBoard()
        board.pieces[1][1] = Piece('white', 'square')
        board.pieces[1][2] = Piece('black', 'square')
        game = GameState(board)

        # Push white at (1,1) up -> into kill zone (0,1)
        result = game.perform_push(1, 1, (-1, 0))
        assert result is True
        # White square pushed into kill zone
        assert game.board.get_piece(1, 1) is None
        assert game.pieces_pushed_off['white']['squares'] == 1

    def test_push_chain_partial_into_kill_zone(self):
        """Push chain where last piece goes into kill zone."""
        board = PushFightBoard()
        board.pieces[7][2] = Piece('white', 'square')
        board.pieces[8][2] = Piece('black', 'square')
        game = GameState(board)

        # Push down: white at (7,2) pushes black at (8,2) toward (9,2) which is kill zone
        result = game.perform_push(7, 2, (1, 0))
        assert result is True
        # White moved to (8,2)
        assert game.board.get_piece(8, 2) is not None
        assert game.board.get_piece(8, 2).team == 'white'
        # Black pushed into kill zone (9,2) - removed
        assert game.pieces_pushed_off['black']['squares'] == 1


# ============================================================
# GameState Tests - has_legal_push
# ============================================================

class TestHasLegalPush:
    def test_initial_position_has_legal_push(self):
        """Initial position should have legal pushes for white."""
        game = GameState.create_initial_game()
        assert game.has_legal_push() is True

    def test_has_legal_push_black(self):
        """Black should also have legal pushes from initial position."""
        game = GameState.create_initial_game()
        game.current_player = 'black'
        assert game.has_legal_push() is True

    def test_no_square_pieces_no_push(self):
        """If a player has no square pieces, they have no legal push."""
        board = PushFightBoard()
        board.pieces[5][0] = Piece('white', 'round')
        board.pieces[5][1] = Piece('white', 'round')
        game = GameState(board)
        assert game.has_legal_push() is False

    def test_single_piece_surrounded_by_rails(self):
        """A single square piece pushed against all side rails has no push."""
        board = PushFightBoard()
        # Place at (4,0) - left side is off-board (side rail), but can push right/up/down
        board.pieces[4][0] = Piece('white', 'square')
        game = GameState(board)
        # Can push right (4,1 is empty), down (5,0 is empty), up (3,0 is empty)
        assert game.has_legal_push() is True


# ============================================================
# GameState Tests - Full Turn Flow
# ============================================================

class TestFullTurnFlow:
    def test_zero_moves_then_push(self):
        """Player can push immediately without making any moves."""
        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        game = GameState(board)

        assert game.moves_made == 0
        result = game.perform_push(5, 1, (1, 0))
        assert result is True
        assert game.push_completed is True
        game.switch_turn()
        assert game.current_player == 'black'

    def test_one_move_then_push(self):
        """Player makes 1 move then pushes."""
        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        board.pieces[5][2] = Piece('white', 'round')
        game = GameState(board)

        # Move the round piece
        assert game.can_move() is True
        game.board.pieces[5][2] = None
        game.board.pieces[6][2] = Piece('white', 'round')
        game.moves_made = 1

        # Push
        assert game.can_push() is True
        result = game.perform_push(5, 1, (1, 0))
        assert result is True
        game.switch_turn()
        assert game.current_player == 'black'

    def test_two_moves_then_push(self):
        """Player makes 2 moves then must push."""
        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        board.pieces[5][2] = Piece('white', 'round')
        board.pieces[3][0] = Piece('white', 'round')
        game = GameState(board)

        # Simulate 2 moves
        game.moves_made = 2
        assert game.can_move() is False
        assert game.can_push() is True

        result = game.perform_push(5, 1, (1, 0))
        assert result is True
        game.switch_turn()
        assert game.current_player == 'black'

    def test_cannot_push_twice(self):
        """After pushing, push_completed is True and can't push again."""
        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        game = GameState(board)

        game.perform_push(5, 1, (1, 0))
        assert game.push_completed is True
        assert game.can_push() is False

    def test_complete_two_turn_cycle(self):
        """White pushes, then black pushes."""
        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        board.pieces[4][1] = Piece('black', 'square')
        game = GameState(board)

        # White pushes down
        game.perform_push(5, 1, (1, 0))
        game.switch_turn()
        assert game.current_player == 'black'

        # Black pushes down
        result = game.perform_push(4, 1, (1, 0))
        assert result is True
        game.switch_turn()
        assert game.current_player == 'white'


# ============================================================
# GameState Tests - Setup Mode
# ============================================================

class TestSetupMode:
    def test_custom_game_is_setup_mode(self):
        game = GameState.create_custom_game()
        assert game.setup_mode is True

    def test_place_piece_on_correct_side(self):
        game = GameState.create_custom_game()
        success, _ = game.place_piece(4, 0, 'white', 'square')
        assert success is True

    def test_place_piece_on_wrong_side(self):
        game = GameState.create_custom_game()
        success, _ = game.place_piece(5, 0, 'white', 'square')
        assert success is False

    def test_place_piece_on_kill_zone(self):
        game = GameState.create_custom_game()
        success, _ = game.place_piece(0, 0, 'white', 'square')
        assert success is False

    def test_place_piece_limit_squares(self):
        game = GameState.create_custom_game()
        for i in range(3):
            game.place_piece(4, i, 'white', 'square')
        success, _ = game.place_piece(3, 0, 'white', 'square')
        assert success is False

    def test_place_piece_limit_rounds(self):
        game = GameState.create_custom_game()
        game.place_piece(4, 0, 'white', 'round')
        game.place_piece(4, 1, 'white', 'round')
        success, _ = game.place_piece(4, 2, 'white', 'round')
        assert success is False

    def test_cannot_place_on_occupied(self):
        game = GameState.create_custom_game()
        game.place_piece(4, 0, 'white', 'square')
        success, _ = game.place_piece(4, 0, 'white', 'round')
        assert success is False

    def test_start_game_requires_full_placement(self):
        game = GameState.create_custom_game()
        can_start, _ = game.can_start_game()
        assert can_start is False

    def test_start_game_full_placement(self):
        game = GameState.create_custom_game()
        # White
        for i in range(3):
            game.place_piece(4, i, 'white', 'square')
        game.place_piece(3, 0, 'white', 'round')
        game.place_piece(3, 1, 'white', 'round')
        # Black
        for i in range(3):
            game.place_piece(5, i, 'black', 'square')
        game.place_piece(6, 0, 'black', 'round')
        game.place_piece(6, 1, 'black', 'round')

        can_start, _ = game.can_start_game()
        assert can_start is True
        success, _ = game.start_game()
        assert success is True
        assert game.setup_mode is False

    def test_remove_piece_in_setup(self):
        game = GameState.create_custom_game()
        game.place_piece(4, 0, 'white', 'square')
        success, _ = game.remove_piece(4, 0)
        assert success is True
        assert game.board.get_piece(4, 0) is None


# ============================================================
# GameState Tests - Serialization
# ============================================================

class TestSerialization:
    def test_game_state_roundtrip(self):
        game = GameState.create_initial_game()
        game.moves_made = 1
        game.current_player = 'black'
        game.pieces_pushed_off['white']['squares'] = 1

        restored = GameState.from_dict(game.to_dict())
        assert restored.current_player == 'black'
        assert restored.moves_made == 1
        assert restored.pieces_pushed_off['white']['squares'] == 1
        assert restored.count_pieces('white') == 5  # Still on board
        assert restored.count_pieces('black') == 5


# ============================================================
# Edge Cases and Bug Regression Tests
# ============================================================

class TestEdgeCases:
    def test_push_own_piece_into_kill_zone(self):
        """It should be possible to push your own piece into a kill zone (bad strategy, but legal)."""
        board = PushFightBoard()
        board.pieces[7][1] = Piece('white', 'square')
        board.pieces[8][1] = Piece('white', 'round')
        game = GameState(board)

        result = game.perform_push(7, 1, (1, 0))
        assert result is True
        # White round pushed into kill zone
        assert game.pieces_pushed_off['white']['rounds'] == 1
        assert game.game_over is True
        assert game.winner == 'black'  # White lost their own round piece

    def test_anchor_cleared_when_pushed_to_kill_zone(self):
        """Anchor should be cleared if pusher's destination is a kill zone."""
        board = PushFightBoard()
        # Piece at (8,1), push down: piece goes to (9,1) which is kill zone
        board.pieces[8][1] = Piece('white', 'square')
        game = GameState(board)

        game.perform_push(8, 1, (1, 0))
        # Anchor should be cleared since (9,1) is kill zone
        assert game.board.anchor_pos == (None, None)

    def test_has_legal_push_detects_side_rail_blocking(self):
        """has_legal_push should correctly handle pushes blocked by side rails."""
        board = PushFightBoard()
        # Put a single square piece at corner where 3 directions are blocked
        # (3,0): left is side rail (-1 col), but up/down/right have space
        board.pieces[3][0] = Piece('white', 'square')
        game = GameState(board)
        # Can push right (3,1 is empty), up (2,0 is empty), down (4,0 is empty)
        assert game.has_legal_push() is True

    def test_push_does_not_move_pieces_past_anchor(self):
        """Anchor blocks the entire push — no pieces move, including downstream."""
        board = PushFightBoard()
        board.pieces[4][1] = Piece('white', 'square')
        board.pieces[5][1] = Piece('black', 'square')
        board.pieces[6][1] = Piece('black', 'round')
        board.anchor_pos = (5, 1)  # Anchor on middle piece
        game = GameState(board)

        # Push down: anchor at (5,1) blocks entire chain
        game.perform_push(4, 1, (1, 0))
        # All pieces stay in place
        assert game.board.get_piece(4, 1) is not None  # white square
        assert game.board.get_piece(5, 1) is not None  # black square (anchored)
        assert game.board.get_piece(6, 1) is not None  # black round (blocked)

    def test_multiple_pieces_pushed_off_same_push(self):
        """A long chain could push multiple pieces off in theory.
        In practice on a 4-wide board this is rare, but test the tracking."""
        board = PushFightBoard()
        game = GameState(board)
        # Manually track to verify counter works
        game.pieces_pushed_off['black']['squares'] = 1
        game.pieces_pushed_off['black']['rounds'] = 0
        assert game.check_game_over() is False  # Only 1 square off

        game.pieces_pushed_off['black']['squares'] = 2
        assert game.check_game_over() is True
        assert game.winner == 'white'


# ============================================================
# Initial Game Piece Names (voice-control feature)
# ============================================================

class TestInitialGamePieceNames:
    """Verify that create_initial_game() assigns jiu-jitsu grip / submission names
    to every piece and that names survive moves and serialization."""

    def setup_method(self):
        self.game = GameState.create_initial_game()

    def _pieces_by_team(self, team):
        """Return all Piece objects on the board for a given team."""
        pieces = []
        for y in range(10):
            for x in range(4):
                p = self.game.board.get_piece(y, x)
                if p and p.team == team:
                    pieces.append(p)
        return pieces

    def test_white_squares_are_sleeve_lapel_belt(self):
        squares = [p for p in self._pieces_by_team('white') if p.shape == 'square']
        names = sorted(p.name for p in squares)
        assert names == ['belt', 'lapel', 'sleeve']

    def test_white_rounds_are_neck_and_joint(self):
        rounds = [p for p in self._pieces_by_team('white') if p.shape == 'round']
        names = sorted(p.name for p in rounds)
        assert names == ['joint', 'neck']

    def test_black_squares_are_sleeve_lapel_belt(self):
        squares = [p for p in self._pieces_by_team('black') if p.shape == 'square']
        names = sorted(p.name for p in squares)
        assert names == ['belt', 'lapel', 'sleeve']

    def test_black_rounds_are_neck_and_joint(self):
        rounds = [p for p in self._pieces_by_team('black') if p.shape == 'round']
        names = sorted(p.name for p in rounds)
        assert names == ['joint', 'neck']

    def test_every_piece_has_a_name(self):
        for y in range(10):
            for x in range(4):
                p = self.game.board.get_piece(y, x)
                if p:
                    assert p.name is not None, f"Piece at ({y},{x}) has no name"

    def test_piece_names_survive_serialization_roundtrip(self):
        restored = GameState.from_dict(self.game.to_dict())
        for y in range(10):
            for x in range(4):
                orig = self.game.board.get_piece(y, x)
                rest = restored.board.get_piece(y, x)
                if orig:
                    assert rest is not None
                    assert rest.name == orig.name, f"Name mismatch at ({y},{x})"

    def test_piece_name_travels_with_piece_after_move(self):
        """Moving a piece must not lose or change its name."""
        # White sleeve is at (4,0) in the default layout
        sleeve = self.game.board.get_piece(4, 0)
        assert sleeve is not None and sleeve.name == 'sleeve'

        # Find a valid destination and move there
        valid = self.game.board.get_valid_moves(4, 0)
        assert valid, "Sleeve at (4,0) should have at least one valid move"
        to_y, to_x = next(iter(valid))
        success, _ = self.game.perform_move((4, 0), (to_y, to_x))
        assert success

        moved = self.game.board.get_piece(to_y, to_x)
        assert moved is not None
        assert moved.name == 'sleeve'
