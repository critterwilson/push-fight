import unittest
from unittest.mock import MagicMock
import sys
import os

# Ensure we can import from app
sys.path.append(os.getcwd())

from app.rag.state_formatter import format_game_state

class TestStateFormatter(unittest.TestCase):
    def test_format_game_state_structure(self):
        """Test that the formatted string contains the expected sections."""
        mock_game = MagicMock()
        mock_game.current_player = "white"
        mock_game.move_log = ["move1", "move2"]
        mock_game.board = "BoardGrid"
        
        formatted = format_game_state(mock_game)
        
        self.assertIn("Current Player: white", formatted)
        self.assertIn("Recent Moves (2 total):", formatted)
        self.assertIn("- move1", formatted)
        self.assertIn("- move2", formatted)
        self.assertIn("Board Configuration:\nBoardGrid", formatted)

    def test_format_game_state_truncates_log(self):
        """Test that only the last 3 moves are shown."""
        mock_game = MagicMock()
        mock_game.current_player = "black"
        # Create 5 moves
        mock_game.move_log = [f"move{i}" for i in range(5)]
        mock_game.board = "BoardGrid"
        
        formatted = format_game_state(mock_game)
        
        self.assertIn("Recent Moves (5 total):", formatted)
        self.assertNotIn("- move0", formatted)
        self.assertNotIn("- move1", formatted)
        self.assertIn("- move2", formatted)
        self.assertIn("- move3", formatted)
        self.assertIn("- move4", formatted)

    def test_format_game_state_handles_missing_attrs(self):
        """Test that the formatter handles missing attributes gracefully."""
        class SimpleGame:
            pass
        
        game = SimpleGame()
        game.current_player = "white"
        # No move_log, no board
        
        formatted = format_game_state(game)
        
        self.assertIn("Current Player: white", formatted)
        self.assertNotIn("Recent Moves", formatted)
        self.assertNotIn("Board Configuration", formatted)

if __name__ == '__main__':
    unittest.main()