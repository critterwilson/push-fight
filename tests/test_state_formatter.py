"""
Tests for the game state formatter (app.rag.state_formatter).

The state formatter converts a GameState object into a human-readable string
that is injected into the RAG prompt context. This allows the AI referee to
"see" the current board position and recent move history when answering
player questions.

Testing strategy:
  - Uses MagicMock to simulate game state objects with configurable attributes
    (current_player, move_log, board).
  - Tests three key behaviors:
    1. Correct section structure (player, moves, board all present).
    2. Move log truncation (only the last 3 moves shown for long histories).
    3. Graceful degradation when optional attributes (move_log, board) are
       missing from the game object — no crash, just omitted sections.
"""

import unittest
from unittest.mock import MagicMock
import sys
import os

# Ensure we can import from app regardless of CWD.
sys.path.append(os.getcwd())

from app.rag.state_formatter import format_game_state


class TestStateFormatter(unittest.TestCase):
    """Tests for format_game_state() output structure and edge cases."""

    def test_format_game_state_structure(self):
        """Verify that the formatted string includes all three expected sections:
        current player, recent moves (with total count), and board configuration.

        Uses a MagicMock game with current_player='white', 2 moves in the log,
        and a dummy board string.
        """
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
        """When the move log has more than 3 entries, only the last 3 should
        be included in the output. This keeps the RAG prompt concise while
        still providing recent context. The total count header must still
        reflect all moves."""
        mock_game = MagicMock()
        mock_game.current_player = "black"
        mock_game.move_log = [f"move{i}" for i in range(5)]
        mock_game.board = "BoardGrid"

        formatted = format_game_state(mock_game)

        self.assertIn("Recent Moves (5 total):", formatted)
        # Oldest two moves should be truncated
        self.assertNotIn("- move0", formatted)
        self.assertNotIn("- move1", formatted)
        # Last three moves should be present
        self.assertIn("- move2", formatted)
        self.assertIn("- move3", formatted)
        self.assertIn("- move4", formatted)

    def test_format_game_state_handles_missing_attrs(self):
        """When the game object is missing move_log or board attributes,
        the formatter must not crash — it should simply omit those sections.
        This supports formatting partial or mock game states."""
        class SimpleGame:
            pass

        game = SimpleGame()
        game.current_player = "white"
        # Deliberately omit move_log and board attributes

        formatted = format_game_state(game)

        self.assertIn("Current Player: white", formatted)
        self.assertNotIn("Recent Moves", formatted)
        self.assertNotIn("Board Configuration", formatted)


if __name__ == '__main__':
    unittest.main()