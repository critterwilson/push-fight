import unittest
from app.engine.game_state import GameState
from app.engine.board import PushFightBoard
from app.engine.pieces import Piece

class TestGameLogging(unittest.TestCase):
    def setUp(self):
        self.game = GameState.create_initial_game()

    def test_log_initialization(self):
        """Test that the move log is initialized as empty."""
        self.assertEqual(self.game.move_log, [])

    def test_perform_move_logging(self):
        """Test that perform_move logs the action correctly."""
        # White moves from (4,0) to (3,0) - valid move
        success, msg = self.game.perform_move((4, 0), (3, 0))
        self.assertTrue(success)
        
        self.assertEqual(len(self.game.move_log), 1)
        entry = self.game.move_log[0]
        self.assertEqual(entry['type'], 'move')
        self.assertEqual(entry['player'], 'white')
        self.assertEqual(entry['from_pos'], (4, 0))
        self.assertEqual(entry['to_pos'], (3, 0))
        self.assertTrue('timestamp' in entry)

    def test_perform_push_logging(self):
        """Test that perform_push logs the action correctly."""
        # Setup a state where a push is valid
        # Move (4, 0) to (3, 0) to open up (4, 0)
        self.game.perform_move((4, 0), (3, 0))
        
        # Now push (4, 1) left into (4, 0)
        success = self.game.perform_push(4, 1, (0, -1))
        self.assertTrue(success)
        
        # Log should have 2 entries: 1 move, 1 push
        self.assertEqual(len(self.game.move_log), 2)
        push_entry = self.game.move_log[1]
        self.assertEqual(push_entry['type'], 'push')
        self.assertEqual(push_entry['player'], 'white')
        self.assertEqual(push_entry['piece'], (4, 1))
        self.assertEqual(push_entry['direction'], (0, -1))
        self.assertTrue('timestamp' in push_entry)

if __name__ == '__main__':
    unittest.main()