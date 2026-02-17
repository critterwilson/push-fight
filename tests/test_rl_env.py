"""Tests for the RL environment."""

import numpy as np
import pytest
from app.rl.env import PushFightEnv
from app.engine.game_state import GameState
from app.engine.pieces import Piece
from app.engine.board import PushFightBoard


class TestObservation:
    def test_observation_shape(self):
        env = PushFightEnv()
        obs, info = env.reset()
        assert obs.shape == (203,), f"Expected (203,), got {obs.shape}"

    def test_observation_range(self):
        env = PushFightEnv()
        obs, info = env.reset()
        assert np.all(obs >= 0.0)
        assert np.all(obs <= 1.0)

    def test_observation_includes_phase(self):
        """Observation should encode phase, moves remaining, and turn."""
        env = PushFightEnv()
        obs, info = env.reset()
        # Last 3 features: [is_push_phase, moves_remaining, is_white_turn]
        is_push_phase = obs[200]
        moves_remaining = obs[201]
        is_white_turn = obs[202]

        assert is_push_phase == 0.0  # Move phase at start
        assert moves_remaining == 1.0  # 2 moves remaining, normalized
        assert is_white_turn == 1.0  # White starts

    def test_observation_is_mine_perspective(self):
        """is_mine feature should reflect current player's perspective."""
        env = PushFightEnv()
        env.reset()

        # White's turn: white pieces should have is_mine=1.0
        obs = env._get_observation()
        # White square at (4,0) in initial position
        # Index into flat obs: (4*4 + 0) * 5 + 1 = 81  (is_mine feature)
        cell_start = (4 * 4 + 0) * 5
        has_piece = obs[cell_start + 0]
        is_mine = obs[cell_start + 1]
        assert has_piece == 1.0
        assert is_mine == 1.0  # White piece, white's turn

        # Black piece at (5,0): should have is_mine=0.0
        cell_start = (5 * 4 + 0) * 5
        has_piece = obs[cell_start + 0]
        is_mine = obs[cell_start + 1]
        assert has_piece == 1.0
        assert is_mine == 0.0  # Black piece, white's turn


class TestActionMasking:
    def test_action_masks_shape(self):
        env = PushFightEnv()
        env.reset()
        mask = env.action_masks()
        assert mask.shape == (1760,)
        assert mask.dtype == bool

    def test_action_masks_has_valid_actions(self):
        env = PushFightEnv()
        env.reset()
        mask = env.action_masks()
        assert np.any(mask), "Should have at least one valid action"

    def test_action_masks_move_phase(self):
        """In move phase, only move actions (0-1599) should be valid."""
        env = PushFightEnv()
        env.reset()
        assert env.current_phase == 'move'
        mask = env.action_masks()
        # No push actions should be valid during move phase
        assert not np.any(mask[1600:]), "Push actions shouldn't be valid during move phase"

    def test_action_masks_push_phase(self):
        """In push phase, only push actions (1600-1759) should be valid."""
        env = PushFightEnv()
        env.reset()
        # Force push phase
        env.current_phase = 'push'
        env.game.moves_made = 2
        mask = env.action_masks()
        # No move actions should be valid during push phase
        assert not np.any(mask[:1600]), "Move actions shouldn't be valid during push phase"
        assert np.any(mask[1600:]), "Should have valid push actions"


class TestStepMovePhase:
    def test_valid_move(self):
        env = PushFightEnv()
        env.reset()
        valid_actions = env._get_valid_actions()
        assert len(valid_actions) > 0

        action = valid_actions[0]
        obs, reward, terminated, truncated, info = env.step(action)
        assert reward >= 0  # No penalty for valid move
        assert info['action_type'] == 'move'
        assert not terminated

    def test_invalid_move_gets_substituted(self):
        env = PushFightEnv()
        env.reset()
        # Action 0 is almost certainly invalid (move piece at (0,0) to (0,0))
        # and (0,0) is a kill zone with no piece
        obs, reward, terminated, truncated, info = env.step(0)
        # Should have substituted with a valid action and applied penalty
        assert reward < 0.01  # Should have -0.1 penalty


class TestStepPushPhase:
    def test_push_executes_once(self):
        """Critical test: push should execute exactly once (bug 2.1 fix)."""
        env = PushFightEnv()
        env.reset()

        # Set up a simple board for predictable push
        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        board.pieces[6][1] = Piece('black', 'square')
        env.game = GameState(board)
        env.current_phase = 'push'
        env.game.moves_made = 2

        # Encode push: piece at (5,1), direction down (1,0) = dir_idx 1
        action = 1600 + 5 * 16 + 1 * 4 + 1

        obs, reward, terminated, truncated, info = env.step(action)
        assert info['action_type'] == 'push'
        # Push should succeed - white pushes black down
        assert reward > -0.5, f"Push should not get -0.5 penalty, got {reward}"

        # Verify pieces moved correctly
        assert env.game.board.get_piece(5, 1) is None  # Pusher moved
        assert env.game.board.get_piece(6, 1) is not None  # Pusher's new position
        assert env.game.board.get_piece(6, 1).team == 'white'
        assert env.game.board.get_piece(7, 1) is not None  # Black piece pushed
        assert env.game.board.get_piece(7, 1).team == 'black'

    def test_push_switches_turn(self):
        """After a valid push, turn should switch."""
        env = PushFightEnv()
        env.reset()

        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        env.game = GameState(board)
        env.current_phase = 'push'
        env.game.moves_made = 2

        assert env.game.current_player == 'white'

        # Push down
        action = 1600 + 5 * 16 + 1 * 4 + 1
        env.step(action)

        assert env.game.current_player == 'black'
        assert env.current_phase == 'move'

    def test_push_into_kill_zone_terminates(self):
        """Pushing a round piece into kill zone should end the game."""
        env = PushFightEnv()
        env.reset()

        board = PushFightBoard()
        board.pieces[7][1] = Piece('white', 'square')
        board.pieces[8][1] = Piece('black', 'round')
        env.game = GameState(board)
        env.current_phase = 'push'
        env.game.moves_made = 2

        # Push down: black round goes to (9,1) which is kill zone
        action = 1600 + 7 * 16 + 1 * 4 + 1
        obs, reward, terminated, truncated, info = env.step(action)

        assert terminated is True
        assert env.game.game_over is True
        assert env.game.winner == 'white'
        assert reward == 1.0  # Win


class TestFullEpisode:
    def test_episode_with_random_valid_actions(self):
        """Run a full episode using only valid actions."""
        env = PushFightEnv()
        obs, info = env.reset()
        total_reward = 0.0
        steps = 0

        while steps < 500:
            mask = env.action_masks()
            valid_actions = np.where(mask)[0]
            if len(valid_actions) == 0:
                break
            action = np.random.choice(valid_actions)
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            steps += 1
            if terminated or truncated:
                break

        assert steps > 0, "Episode should have at least one step"
        # With valid actions only, we should never get the -0.1 substitution penalty
        # (except potentially on the very edge of phase transitions)

    def test_episode_terminates(self):
        """Episodes should eventually terminate (via game end or truncation)."""
        env = PushFightEnv()
        obs, info = env.reset()
        done = False
        steps = 0

        while not done and steps < 1000:
            mask = env.action_masks()
            valid_actions = np.where(mask)[0]
            if len(valid_actions) == 0:
                break
            action = np.random.choice(valid_actions)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            steps += 1

        assert done, f"Episode should terminate within 1000 steps, got {steps}"


class TestEpisodeLengthLimit:
    def test_truncation_at_max_steps(self):
        """Episode should truncate at max_steps."""
        env = PushFightEnv()
        env.max_steps = 10  # Set very low for testing
        obs, info = env.reset()

        for i in range(15):
            mask = env.action_masks()
            valid = np.where(mask)[0]
            if len(valid) == 0:
                break
            obs, reward, terminated, truncated, info = env.step(valid[0])
            if terminated or truncated:
                break

        assert truncated or terminated, "Should have ended by step 10"


class TestNoValidActionsFallback:
    def test_empty_valid_actions_terminates(self):
        """When no valid actions exist, the game should end."""
        env = PushFightEnv()
        env.reset()

        # Set up a state with no valid actions (no square pieces for current player)
        board = PushFightBoard()
        board.pieces[5][0] = Piece('white', 'round')
        env.game = GameState(board)
        env.current_phase = 'push'
        env.game.moves_made = 2

        obs, reward, terminated, truncated, info = env.step(0)
        assert terminated is True
        assert reward == -1.0


class TestDecodeAction:
    def test_decode_move_action(self):
        env = PushFightEnv()
        env.reset()
        # Decode action for move: piece at (4,0) to (3,0)
        action = 4 * 160 + 0 * 40 + 3 * 4 + 0
        phase, data = env._decode_action(action)
        assert phase == 'move'
        assert data == (4, 0, 3, 0)

    def test_decode_push_action(self):
        env = PushFightEnv()
        env.reset()
        env.current_phase = 'push'
        env.game.moves_made = 2
        # Decode push: piece at (4,0), direction down (idx 1)
        action = 1600 + 4 * 16 + 0 * 4 + 1
        phase, data = env._decode_action(action)
        assert phase == 'push'
        assert data == (4, 0, (1, 0))

    def test_decode_invalid_returns_none(self):
        env = PushFightEnv()
        env.reset()
        # Push action during move phase
        phase, data = env._decode_action(1700)
        assert phase is None


class TestIsValidPush:
    def test_valid_push(self):
        env = PushFightEnv()
        env.reset()
        # White square at (4,0), push down into (5,0) which has black square
        # Landing spot would be after the chain
        assert env._is_valid_push(4, 0, (1, 0)) is True

    def test_invalid_push_empty_square(self):
        env = PushFightEnv()
        env.reset()
        assert env._is_valid_push(3, 0, (1, 0)) is False  # (3,0) is empty initially? No, (3,1) has white round

    def test_invalid_push_round_piece(self):
        env = PushFightEnv()
        env.reset()
        # (4,3) has white round - can't push with round
        assert env._is_valid_push(4, 3, (1, 0)) is False

    def test_invalid_push_opponent_piece(self):
        env = PushFightEnv()
        env.reset()
        # (5,0) has black square - can't push opponent's piece
        assert env._is_valid_push(5, 0, (1, 0)) is False

    def test_invalid_push_side_rail(self):
        env = PushFightEnv()
        env.reset()
        # (4,0) push left - goes off board
        assert env._is_valid_push(4, 0, (0, -1)) is False
