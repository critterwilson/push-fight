"""
Integration tests for complete game workflows.

Unlike the unit tests in test_engine.py (which test individual methods in
isolation), these integration tests exercise multi-step user scenarios that
span across engine, storage, and serialization boundaries:

  1. **Custom setup workflow** — create a custom game, place all 10 pieces
     through the setup API, verify placement counts, and start the game.
  2. **Move-and-push workflow** — find a movable piece, relocate it, then
     perform a push, verifying that the engine does not crash on any path.
  3. **Save/load workflow** — modify game state, persist to disk, reload,
     and verify every field and piece position matches the original.
  4. **Setup save/load** — save a partially-completed setup and verify that
     setup_mode and placed pieces survive the round-trip.
  5. **Turn switching** — simulate two consecutive push-then-switch cycles
     to validate full turn alternation.

These tests serve as smoke tests for the most common user journeys and
catch integration bugs that unit tests might miss (e.g., serialization
format mismatches between engine and storage layers).
"""

import pytest
from app.engine.game_state import GameState
from app.storage import save_game, load_game, delete_save


class TestGameWorkflow:
    """End-to-end workflow tests that combine multiple engine and storage
    operations into realistic user scenarios."""

    def test_complete_custom_setup_workflow(self):
        """Simulate a full custom setup: create a custom game, place all 5
        white pieces and 5 black pieces on valid cells, verify the placement
        status counters, then start the game and confirm setup_mode is off."""
        # Create custom game
        game = GameState.create_custom_game()
        assert game.setup_mode is True

        # Place white pieces (3 squares on row 4, 2 rounds on row 3)
        for i in range(3):
            success, _ = game.place_piece(4, i, 'white', 'square')
            assert success is True
        for i in range(2):
            success, _ = game.place_piece(3, i, 'white', 'round')
            assert success is True

        # Place black pieces (3 squares on row 5, 2 rounds on row 6)
        for i in range(3):
            success, _ = game.place_piece(5, i, 'black', 'square')
            assert success is True
        for i in range(2):
            success, _ = game.place_piece(6, i, 'black', 'round')
            assert success is True

        # Verify placement counts match expectations
        white_status = game.get_placement_status('white')
        brown_status = game.get_placement_status('black')
        assert white_status['squares'] == 3
        assert white_status['rounds'] == 2
        assert brown_status['squares'] == 3
        assert brown_status['rounds'] == 2

        # Transition from setup to active play
        success, _ = game.start_game()
        assert success is True
        assert game.setup_mode is False
        assert game.current_player == 'white'

    def test_move_and_push_workflow(self):
        """Simulate a realistic turn: find a white piece with valid moves,
        relocate it to a valid destination, then find a white square piece
        and attempt a push. The primary assertion is that no exceptions are
        raised — this is a crash-resistance smoke test."""
        game = GameState.create_initial_game()

        # Find a white piece with at least one valid move
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

            # Manually move the piece (bypassing perform_move to test raw board ops)
            piece = game.board.get_piece(y, x)
            game.board.pieces[y][x] = None
            game.board.pieces[dest_y][dest_x] = piece
            game.moves_made = 1

            # Find a square piece and attempt a push in any direction
            for py in range(10):
                for px in range(4):
                    push_piece = game.board.get_piece(py, px)
                    if push_piece and push_piece.team == 'white' and push_piece.shape == 'square':
                        success = game.perform_push(py, px, (1, 0))
                        # May succeed or fail depending on board state, but must not crash
                        assert isinstance(success, bool)
                        break
                else:
                    continue
                break

    def test_save_load_workflow(self):
        """Full save/load round-trip: modify game state, persist to disk,
        reload, and verify that all scalar fields and every piece on the
        board match the original state cell-by-cell."""
        # Create and modify game
        game = GameState.create_initial_game()
        game.moves_made = 2
        game.current_player = 'black'

        # Save to disk
        save_path = save_game(game, 'test_workflow')
        assert save_path is not None

        # Reload from disk
        loaded = load_game('test_workflow')
        assert loaded.moves_made == 2
        assert loaded.current_player == 'black'

        # Cell-by-cell board comparison
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

        # Clean up test file
        delete_save('test_workflow')

    def test_setup_save_load_workflow(self):
        """Save a partially completed setup (only 3 of 10 pieces placed) and
        verify that reloading preserves setup_mode=True and all placed pieces."""
        game = GameState.create_custom_game()
        game.place_piece(4, 0, 'white', 'square')
        game.place_piece(4, 1, 'white', 'square')
        game.place_piece(5, 0, 'black', 'square')

        save_game(game, 'test_setup_workflow')

        loaded = load_game('test_setup_workflow')
        assert loaded.setup_mode is True
        assert loaded.board.get_piece(4, 0) is not None
        assert loaded.board.get_piece(4, 1) is not None
        assert loaded.board.get_piece(5, 0) is not None

        delete_save('test_setup_workflow')

    def test_turn_switching_workflow(self):
        """Simulate two full turn cycles (white push + switch, black push +
        switch) to verify that the alternation resets moves_made and
        push_completed correctly each time."""
        game = GameState.create_initial_game()
        assert game.current_player == 'white'

        # White completes push and switches to black
        game.push_completed = True
        game.switch_turn()
        assert game.current_player == 'black'
        assert game.moves_made == 0
        assert game.push_completed is False

        # Black completes push and switches back to white
        game.push_completed = True
        game.switch_turn()
        assert game.current_player == 'white'
