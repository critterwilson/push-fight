"""
Tests for the game action logging system (move_log on GameState).

The move_log is an append-only list of dictionaries that records every move
and push action taken during a game. Each log entry includes:
  - type: 'move' or 'push'
  - player: 'white' or 'black'
  - from_pos/to_pos (for moves) or piece/direction (for pushes)
  - timestamp: ISO-format datetime string

The move log is used by the RAG state formatter to provide recent move
history to the AI referee, and could also be used for game replays or
analytics.

Testing strategy:
  - Uses a fresh initial game (via setUp) for each test.
  - Verifies the log starts empty on a new game.
  - Performs a valid move and checks that a correctly structured log entry
    appears with all expected fields.
  - Performs a move followed by a push and verifies both entries are logged
    with correct types and field values.
"""

import unittest
from app.engine.game_state import GameState
from app.engine.board import PushFightBoard
from app.engine.pieces import Piece


class TestGameLogging(unittest.TestCase):
    """Tests for the move_log action logging on GameState.

    Each test starts with a fresh initial game created in setUp.
    """

    def setUp(self):
        """Create a fresh initial game before each test. The initial game has
        all 10 pieces in the standard layout and white to move."""
        self.game = GameState.create_initial_game()

    def test_log_initialization(self):
        """A newly created game must have an empty move_log list. No actions
        have been taken yet, so nothing should be logged."""
        self.assertEqual(self.game.move_log, [])

    def test_perform_move_logging(self):
        """After perform_move succeeds, exactly one log entry should appear
        with type='move', the correct player, source/destination positions,
        and a timestamp field."""
        # White's sleeve at (4,0) slides to (3,0) — adjacent empty cell
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
        """After a move followed by a push, the log should have 2 entries.
        The push entry must have type='push' with the piece position,
        direction vector, player, and timestamp.

        Setup: move (4,0) to (3,0) to vacate (4,0), then push (4,1) left
        into the now-empty (4,0).
        """
        # Move white sleeve out of the way to create space for a push
        self.game.perform_move((4, 0), (3, 0))

        # Push white lapel at (4,1) left into the vacated (4,0)
        success = self.game.perform_push(4, 1, (0, -1))
        self.assertTrue(success)

        # Log should have 2 entries: 1 move + 1 push
        self.assertEqual(len(self.game.move_log), 2)
        push_entry = self.game.move_log[1]
        self.assertEqual(push_entry['type'], 'push')
        self.assertEqual(push_entry['player'], 'white')
        self.assertEqual(push_entry['piece'], (4, 1))
        self.assertEqual(push_entry['direction'], (0, -1))
        self.assertTrue('timestamp' in push_entry)


if __name__ == '__main__':
    unittest.main()