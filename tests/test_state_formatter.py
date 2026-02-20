"""
Tests for the game state formatter (app.rag.state_formatter).

The state formatter converts a GameState object into a human-readable string
that is injected into the RAG prompt context.  Tests use real GameState objects
from the engine rather than mocks, since the formatter calls board methods
(get_valid_moves, get_push_chain, get_placement_status).
"""

import sys
import os
import unittest

sys.path.append(os.getcwd())

from app.rag.state_formatter import format_game_state, _coord
from app.engine.game_state import GameState
from app.engine.board import PushFightBoard
from app.engine.pieces import Piece


class TestCoordHelper(unittest.TestCase):
    """Tests for the _coord(x, y) helper."""

    def test_top_left(self):
        self.assertEqual(_coord(0, 0), "A1")

    def test_bottom_right(self):
        self.assertEqual(_coord(3, 9), "D10")

    def test_middle(self):
        self.assertEqual(_coord(1, 4), "B5")


class TestSetupPhase(unittest.TestCase):
    """Tests for the formatter output during the setup (placement) phase."""

    def test_empty_board_shows_all_pieces_needed(self):
        game = GameState.create_custom_game()
        output = format_game_state(game)

        self.assertIn("Phase: Setup (placing pieces).", output)
        self.assertIn("White needs to place: 3 square, 2 round", output)
        self.assertIn("Black needs to place: 3 square, 2 round", output)

    def test_partial_placement_shows_remaining(self):
        game = GameState.create_custom_game()
        game.place_piece(4, 0, 'white', 'square', 'sleeve')
        game.place_piece(4, 1, 'white', 'square', 'lapel')
        output = format_game_state(game)

        self.assertIn("White needs to place: 1 square, 2 round", output)
        # Unplaced pieces should be listed
        self.assertIn("belt", output)
        self.assertIn("neck", output)
        self.assertIn("joint", output)

    def test_complete_placement_shows_done(self):
        game = GameState.create_custom_game()
        # Place all 5 white pieces
        game.place_piece(4, 0, 'white', 'square', 'sleeve')
        game.place_piece(4, 1, 'white', 'square', 'lapel')
        game.place_piece(4, 2, 'white', 'square', 'belt')
        game.place_piece(4, 3, 'white', 'round', 'neck')
        game.place_piece(3, 1, 'white', 'round', 'joint')
        output = format_game_state(game)

        self.assertIn("White placement complete (5/5).", output)

    def test_no_valid_moves_section_in_setup(self):
        game = GameState.create_custom_game()
        output = format_game_state(game)

        self.assertNotIn("Valid moves:", output)
        self.assertNotIn("Valid pushes", output)


class TestMovePhase(unittest.TestCase):
    """Tests for the formatter output during the move phase."""

    def test_shows_valid_moves_per_piece(self):
        game = GameState.create_initial_game()
        output = format_game_state(game)

        self.assertIn("Phase: MOVE (2 move(s) remaining", output)
        self.assertIn("Valid moves:", output)
        # White's pieces should have move destinations listed
        self.assertIn("sleeve at A5:", output)
        self.assertIn("can move to", output)

    def test_shows_skip_tip(self):
        game = GameState.create_initial_game()
        output = format_game_state(game)

        self.assertIn("You may also skip remaining moves and push now.", output)

    def test_after_one_move_shows_one_remaining(self):
        game = GameState.create_initial_game()
        game.perform_move((4, 0), (3, 0))  # sleeve slides up
        output = format_game_state(game)

        self.assertIn("Phase: MOVE (1 move(s) remaining", output)
        self.assertIn("Valid moves:", output)

    def test_blocked_piece_shows_blocked(self):
        """A piece surrounded by other pieces should show 'blocked'."""
        board = PushFightBoard()
        # Place a piece with no empty neighbors
        board.pieces[4][1] = Piece('white', 'square', name='lapel')
        board.pieces[3][1] = Piece('white', 'round', name='joint')
        board.pieces[4][0] = Piece('white', 'square', name='sleeve')
        board.pieces[4][2] = Piece('white', 'square', name='belt')
        board.pieces[5][1] = Piece('black', 'square', name='sleeve')
        game = GameState(board)
        output = format_game_state(game)

        self.assertIn("lapel at B5: blocked (no valid moves)", output)

    def test_anchored_piece_shows_anchored(self):
        """The anchored piece should be marked as 'anchored (cannot move)'."""
        game = GameState.create_initial_game()
        # Simulate an anchor on white's sleeve at A5 (row 4, col 0)
        game.board.anchor_pos = (4, 0)
        output = format_game_state(game)

        self.assertIn("sleeve at A5: anchored (cannot move)", output)


class TestPushPhase(unittest.TestCase):
    """Tests for the formatter output during the push phase."""

    def test_shows_valid_pushes(self):
        game = GameState.create_initial_game()
        # Use both moves to enter push phase
        game.perform_move((4, 0), (2, 0))  # sleeve slides up 2
        game.perform_move((3, 1), (3, 0))  # joint slides left
        output = format_game_state(game)

        self.assertIn("Phase: PUSH (must push now", output)
        self.assertIn("Valid pushes (must push now):", output)
        # Square pieces should have push directions listed
        self.assertIn("can push", output)

    def test_no_valid_moves_section_in_push_phase(self):
        game = GameState.create_initial_game()
        game.moves_made = 2
        output = format_game_state(game)

        self.assertNotIn("Valid moves:", output)
        self.assertIn("Valid pushes", output)

    def test_push_directions_are_named(self):
        game = GameState.create_initial_game()
        game.moves_made = 2
        output = format_game_state(game)

        # Directions should use human-readable names
        has_direction = any(d in output for d in ["up", "down", "left", "right"])
        self.assertTrue(has_direction, "Push directions should use named directions (up/down/left/right)")


class TestGameOver(unittest.TestCase):
    """Tests for the formatter output when the game is over."""

    def test_shows_game_over(self):
        game = GameState.create_initial_game()
        game.game_over = True
        game.winner = 'black'
        output = format_game_state(game)

        self.assertIn("GAME OVER. Winner: black.", output)
        self.assertIn("No actions available (game is over).", output)

    def test_no_valid_moves_or_pushes(self):
        game = GameState.create_initial_game()
        game.game_over = True
        game.winner = 'white'
        output = format_game_state(game)

        self.assertNotIn("Valid moves:", output)
        self.assertNotIn("Valid pushes", output)


class TestPieceInventoryAndAnchor(unittest.TestCase):
    """Tests for piece inventory and anchor sections (unchanged behavior)."""

    def test_piece_inventory_lists_all_pieces(self):
        game = GameState.create_initial_game()
        output = format_game_state(game)

        self.assertIn("White pieces:", output)
        self.assertIn("Black pieces:", output)
        self.assertIn("sleeve (square) at A5", output)
        self.assertIn("joint (round) at B4", output)

    def test_anchor_none_on_first_turn(self):
        game = GameState.create_initial_game()
        output = format_game_state(game)

        self.assertIn("Anchor: none (first turn or cleared).", output)

    def test_eliminations_none(self):
        game = GameState.create_initial_game()
        output = format_game_state(game)

        self.assertIn("Eliminations: none.", output)


if __name__ == '__main__':
    unittest.main()
