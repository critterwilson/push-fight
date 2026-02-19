"""Tests for the RL environment."""

import numpy as np
import pytest
from app.rl.env import PushFightEnv
from app.engine.game_state import GameState
from app.engine.pieces import Piece
from app.engine.board import PushFightBoard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_env_in_setup_mode():
    """Return an env manually placed into setup mode (for testing setup logic)."""
    env = PushFightEnv()
    env.reset()
    env.game = GameState.create_custom_game()
    env.current_phase = 'setup'
    env.step_count = 0
    return env


def _complete_setup(env):
    """Step the env through a full setup phase using valid placements."""
    assert env.current_phase == 'setup', "Expected env to be in setup phase"
    for _ in range(10):  # 5 white + 5 black pieces
        if env.current_phase != 'setup':
            break
        mask = env.action_masks()
        valid = np.where(mask)[0]
        assert len(valid) > 0, "No valid placement actions"
        env.step(valid[0])
    assert env.current_phase == 'move', "Setup should be complete"


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------

class TestObservation:
    def test_observation_shape(self):
        env = PushFightEnv()
        obs, info = env.reset()
        assert obs.shape == (205,), f"Expected (205,), got {obs.shape}"

    def test_observation_range(self):
        env = PushFightEnv()
        obs, info = env.reset()
        assert np.all(obs >= 0.0)
        assert np.all(obs <= 1.0)

    def test_observation_scalars_at_reset(self):
        """At reset (move phase, white to move, 2 rounds each side):
        is_push_phase=0, moves_remaining=1.0, is_white_turn=1,
        own_rounds=1.0, opp_rounds=1.0."""
        env = PushFightEnv()
        obs, info = env.reset()
        assert obs[200] == 0.0   # is_push_phase — not in push phase
        assert obs[201] == 1.0   # moves_remaining — 2 moves available (2/2)
        assert obs[202] == 1.0   # is_white_turn — white starts
        assert obs[203] == 1.0   # own_rounds — 2 round pieces alive (2/2)
        assert obs[204] == 1.0   # opp_rounds — 2 round pieces alive (2/2)

    def test_observation_is_mine_perspective(self):
        """is_mine feature should reflect current player's perspective."""
        env = PushFightEnv()
        env.reset()
        obs = env._get_observation()
        # White's turn: white pieces should have is_mine=1.0
        found_mine = False
        for y in range(10):
            for x in range(4):
                piece = env.game.board.get_piece(y, x)
                if piece and piece != "OUT_OF_BOUNDS" and piece.team == 'white':
                    cell_start = (y * 4 + x) * 5
                    if obs[cell_start + 1] == 1.0:
                        found_mine = True
        assert found_mine, "White pieces should have is_mine=1.0 on white's turn"

    def test_observation_rounds_drop_when_piece_pushed_off(self):
        """own_rounds (obs[203]) decreases when a round piece is pushed off."""
        env = PushFightEnv()
        env.reset()
        obs_before = env._get_observation()
        assert obs_before[204] == 1.0  # opp_rounds starts at 1.0

        # Manually remove one of black's round pieces to simulate a push-off
        for y in range(10):
            for x in range(4):
                piece = env.game.board.get_piece(y, x)
                if piece and piece != "OUT_OF_BOUNDS" and piece.team == 'black' and piece.shape == 'round':
                    env.game.board.pieces[y][x] = None
                    break

        obs_after = env._get_observation()
        assert obs_after[204] == 0.5  # opp_rounds should now be 0.5 (1/2)


# ---------------------------------------------------------------------------
# Action masking
# ---------------------------------------------------------------------------

class TestActionMasking:
    def test_action_masks_shape(self):
        env = PushFightEnv()
        env.reset()
        mask = env.action_masks()
        assert mask.shape == (1800,)
        assert mask.dtype == bool

    def test_action_masks_has_valid_actions(self):
        env = PushFightEnv()
        env.reset()
        mask = env.action_masks()
        assert np.any(mask), "Should have at least one valid action"

    def test_action_masks_move_phase(self):
        """In move phase, only move actions (0–1599) should be valid."""
        env = PushFightEnv()
        env.reset()
        assert env.current_phase == 'move'
        mask = env.action_masks()
        assert not np.any(mask[1600:]), "Push/place actions shouldn't be valid during move phase"

    def test_action_masks_push_phase(self):
        """In push phase, only push actions (1600–1759) should be valid."""
        env = PushFightEnv()
        env.reset()
        env.current_phase = 'push'
        env.game.moves_made = 2
        mask = env.action_masks()
        assert not np.any(mask[:1600]), "Move actions shouldn't be valid during push phase"
        assert not np.any(mask[1760:]), "Placement actions shouldn't be valid during push phase"
        assert np.any(mask[1600:1760]), "Should have valid push actions"


# ---------------------------------------------------------------------------
# Setup phase (tested by manually entering setup mode)
# ---------------------------------------------------------------------------

class TestSetupPhase:
    def test_setup_action_masks_only_placement_range(self):
        """During setup, only placement actions (1760–1799) should be valid."""
        env = _setup_env_in_setup_mode()
        assert env.current_phase == 'setup'
        mask = env.action_masks()
        assert not np.any(mask[:1760]), "Move/push actions should not be valid during setup"
        assert np.any(mask[1760:1800]), "Placement actions should be valid during setup"

    def test_setup_masks_own_side_only_white(self):
        """White cannot place on black's rows (5–9)."""
        env = _setup_env_in_setup_mode()
        assert env.game.current_player == 'white'
        mask = env.action_masks()
        for y in range(5, 10):
            for x in range(4):
                idx = 1760 + y * 4 + x
                assert not mask[idx], f"White should not place at row {y}"

    def test_setup_masks_kill_zones_excluded(self):
        """Kill zone cells should never be valid placements."""
        env = _setup_env_in_setup_mode()
        mask = env.action_masks()
        kill_zone_idx = 1760 + 0 * 4 + 0
        assert not mask[kill_zone_idx], "Kill zone should not be a valid placement"

    def test_setup_step_places_piece_on_board(self):
        """Taking a placement step adds a piece to the board."""
        env = _setup_env_in_setup_mode()
        before = sum(
            1 for y in range(10) for x in range(4)
            if env.game.board.get_piece(y, x)
        )
        mask = env.action_masks()
        valid = np.where(mask)[0]
        env.step(valid[0])
        after = sum(
            1 for y in range(10) for x in range(4)
            if env.game.board.get_piece(y, x)
        )
        assert after == before + 1, "One piece should have been placed"

    def test_setup_completes_after_10_placements(self):
        """After 10 placement steps (5 per team), phase transitions to 'move'."""
        env = _setup_env_in_setup_mode()
        _complete_setup(env)
        assert env.current_phase == 'move'
        assert not env.game.setup_mode

    def test_setup_placement_reward_positive(self):
        """Valid placement step should yield non-negative reward."""
        env = _setup_env_in_setup_mode()
        mask = env.action_masks()
        valid = np.where(mask)[0]
        _, reward, _, _, info = env.step(valid[0])
        assert reward >= 0.0, "Valid placement should not be penalised"
        assert info['action_type'] == 'place'

    def test_setup_center_placement_gives_higher_reward(self):
        """Center-column placements should yield more reward than corner placements."""
        env = _setup_env_in_setup_mode()
        center_action = 1760 + 4 * 4 + 1  # Row 4, col 1 — center column
        env2 = _setup_env_in_setup_mode()
        corner_action = 1760 + 4 * 4 + 0  # Row 4, col 0

        if env.action_masks()[center_action] and env2.action_masks()[corner_action]:
            _, r_center, _, _, _ = env.step(center_action)
            _, r_corner, _, _, _ = env2.step(corner_action)
            assert r_center > r_corner, "Central placement should reward more"

    def test_setup_switches_to_opponent_after_team_completes(self):
        """After white places 5 pieces, current_player should switch to black."""
        env = _setup_env_in_setup_mode()
        assert env.game.current_player == 'white'
        for _ in range(5):
            mask = env.action_masks()
            valid = np.where(mask)[0]
            env.step(valid[0])
            if env.game.current_player == 'black':
                break
        assert env.game.current_player == 'black', "Should switch to black after white places all pieces"
        assert env.current_phase == 'setup', "Still in setup while black places pieces"


# ---------------------------------------------------------------------------
# Step: move phase
# ---------------------------------------------------------------------------

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
        # Action 0 is almost certainly invalid during move phase (no piece at 0,0)
        obs, reward, terminated, truncated, info = env.step(0)
        assert reward < 0.01  # Should have -0.05 penalty


# ---------------------------------------------------------------------------
# Step: push phase
# ---------------------------------------------------------------------------

class TestStepPushPhase:
    def test_push_executes_once(self):
        """Critical test: push should execute exactly once."""
        env = PushFightEnv()
        env.reset()

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
        assert reward > -0.5, f"Push should not get -0.5 penalty, got {reward}"

        assert env.game.board.get_piece(5, 1) is None
        assert env.game.board.get_piece(6, 1) is not None
        assert env.game.board.get_piece(6, 1).team == 'white'
        assert env.game.board.get_piece(7, 1) is not None
        assert env.game.board.get_piece(7, 1).team == 'black'

    def test_push_switches_turn(self):
        env = PushFightEnv()
        env.reset()

        board = PushFightBoard()
        board.pieces[5][1] = Piece('white', 'square')
        env.game = GameState(board)
        env.current_phase = 'push'
        env.game.moves_made = 2

        assert env.game.current_player == 'white'
        action = 1600 + 5 * 16 + 1 * 4 + 1
        env.step(action)

        assert env.game.current_player == 'black'
        assert env.current_phase == 'move'

    def test_push_into_kill_zone_terminates(self):
        env = PushFightEnv()
        env.reset()

        board = PushFightBoard()
        board.pieces[7][1] = Piece('white', 'square')
        board.pieces[8][1] = Piece('black', 'round')
        env.game = GameState(board)
        env.current_phase = 'push'
        env.game.moves_made = 2

        action = 1600 + 7 * 16 + 1 * 4 + 1
        obs, reward, terminated, truncated, info = env.step(action)

        assert terminated is True
        assert env.game.game_over is True
        assert env.game.winner == 'white'
        assert reward == 1.0

    def test_push_round_threat_bonus(self):
        """Pushing an opponent round piece to edge_dist ≤ 1 earns ROUND_THREAT_REWARD."""
        from app.rl.env import ROUND_THREAT_REWARD
        env = PushFightEnv()
        env.reset()

        # White square at (6,1), black round at (7,1) — pushing down moves black round to (8,1)
        # _edge_dist(8,1) = min(8, 1, 1, 2) = 1  → threat bonus should apply
        board = PushFightBoard()
        board.pieces[6][1] = Piece('white', 'square')
        board.pieces[7][1] = Piece('black', 'round')
        env.game = GameState(board)
        env.current_phase = 'push'
        env.game.moves_made = 2

        action = 1600 + 6 * 16 + 1 * 4 + 1  # push down
        _, reward, terminated, truncated, _ = env.step(action)

        assert not terminated, "Black round piece should still be on board at (8,1)"
        assert reward >= ROUND_THREAT_REWARD, (
            f"Expected round threat bonus ≥ {ROUND_THREAT_REWARD}, got {reward}"
        )


# ---------------------------------------------------------------------------
# Full episode
# ---------------------------------------------------------------------------

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

    def test_episode_terminates(self):
        """Episodes should eventually terminate."""
        env = PushFightEnv()
        obs, info = env.reset()
        done = False
        steps = 0

        while not done and steps < 500:
            mask = env.action_masks()
            valid_actions = np.where(mask)[0]
            if len(valid_actions) == 0:
                break
            action = np.random.choice(valid_actions)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            steps += 1

        assert done, f"Episode should terminate within 500 steps, got {steps}"


# ---------------------------------------------------------------------------
# Episode length limit
# ---------------------------------------------------------------------------

class TestEpisodeLengthLimit:
    def test_truncation_at_max_steps(self):
        env = PushFightEnv()
        env.max_steps = 10
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


# ---------------------------------------------------------------------------
# No valid actions fallback
# ---------------------------------------------------------------------------

class TestNoValidActionsFallback:
    def test_empty_valid_actions_terminates(self):
        """When no valid actions exist, the game should end."""
        env = PushFightEnv()
        env.reset()

        board = PushFightBoard()
        board.pieces[5][0] = Piece('white', 'round')
        env.game = GameState(board)
        env.current_phase = 'push'
        env.game.moves_made = 2

        obs, reward, terminated, truncated, info = env.step(0)
        assert terminated is True
        assert reward == -1.0


# ---------------------------------------------------------------------------
# Decode action
# ---------------------------------------------------------------------------

class TestDecodeAction:
    def test_decode_move_action(self):
        env = PushFightEnv()
        env.reset()
        action = 4 * 160 + 0 * 40 + 3 * 4 + 0
        phase, data = env._decode_action(action)
        assert phase == 'move'
        assert data == (4, 0, 3, 0)

    def test_decode_push_action(self):
        env = PushFightEnv()
        env.reset()
        env.current_phase = 'push'
        env.game.moves_made = 2
        action = 1600 + 4 * 16 + 0 * 4 + 1
        phase, data = env._decode_action(action)
        assert phase == 'push'
        assert data == (4, 0, (1, 0))

    def test_decode_setup_action(self):
        env = _setup_env_in_setup_mode()
        # Place at row 4, col 2 → 1760 + 4*4 + 2 = 1778
        action = 1760 + 4 * 4 + 2
        phase, data = env._decode_action(action)
        assert phase == 'place'
        assert data == (4, 2)

    def test_decode_invalid_returns_none(self):
        env = PushFightEnv()
        env.reset()
        # Push action during move phase should return None
        phase, data = env._decode_action(1700)
        assert phase is None


# ---------------------------------------------------------------------------
# Is valid push
# ---------------------------------------------------------------------------

class TestIsValidPush:
    def _env_with_pieces(self):
        """Return an env with the standard starting position in push phase."""
        env = PushFightEnv()
        env.reset()
        env.current_phase = 'push'
        env.game.moves_made = 2
        return env

    def test_valid_push(self):
        env = self._env_with_pieces()
        assert env._is_valid_push(4, 0, (1, 0)) is True

    def test_invalid_push_empty_square(self):
        env = self._env_with_pieces()
        assert env._is_valid_push(3, 0, (1, 0)) is False

    def test_invalid_push_round_piece(self):
        env = self._env_with_pieces()
        assert env._is_valid_push(4, 3, (1, 0)) is False

    def test_invalid_push_opponent_piece(self):
        env = self._env_with_pieces()
        assert env._is_valid_push(5, 0, (1, 0)) is False

    def test_invalid_push_side_rail(self):
        env = self._env_with_pieces()
        assert env._is_valid_push(4, 0, (0, -1)) is False
