"""
Tests for the Push Fight reinforcement learning environment (app.rl.env).

The PushFightEnv wraps the game engine as a Gymnasium-compatible environment
with masked action spaces, enabling training with MaskablePPO. The action
space is divided into three ranges:

  - Actions 0-1599:    Move actions (piece selection + destination)
  - Actions 1600-1759: Push actions (piece selection + direction)
  - Actions 1760-1799: Placement actions (setup phase only)

This module tests:
  - Observation vector shape, value range, and semantic correctness.
  - Action mask shape, dtype, and phase-dependent validity.
  - Setup phase: placement masks, board modifications, phase transitions,
    reward shaping for central vs. corner placements.
  - Move phase: valid/invalid action handling, reward signals.
  - Push phase: execution correctness, turn switching, kill-zone termination,
    round-threat bonus reward shaping.
  - Full episode execution with random valid actions.
  - Episode length truncation.
  - Fallback behavior when no valid actions exist.
  - Action decoding for all three action types (move, push, place).
  - Push validation predicates.
"""

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
    """Create a PushFightEnv and manually override its state to be in setup
    mode with an empty custom game. This bypasses the normal reset flow
    (which starts in move phase with the standard layout) so that setup-
    specific logic can be tested in isolation."""
    env = PushFightEnv()
    env.reset()
    env.game = GameState.create_custom_game()
    env.current_phase = 'setup'
    env.step_count = 0
    return env


def _complete_setup(env):
    """Drive the env through a full setup phase by taking valid placement
    actions until the phase transitions from 'setup' to 'move'. Asserts
    that valid placement actions are always available during setup and that
    the phase correctly transitions after all 10 pieces are placed."""
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
    """Tests for the observation vector returned by the environment.

    The observation is a flat numpy array of 205 floats in [0, 1]:
      - Indices 0-199: 40 cells x 5 features each (is_occupied, is_mine,
        is_square, is_round, is_anchor).
      - Index 200: is_push_phase (0.0 = move phase, 1.0 = push phase).
      - Index 201: moves_remaining (normalized: 2/2 = 1.0, 1/2 = 0.5, 0/2 = 0.0).
      - Index 202: is_white_turn (1.0 = white, 0.0 = black).
      - Index 203: own_rounds (normalized: 2/2 = 1.0, 1/2 = 0.5).
      - Index 204: opp_rounds (normalized: 2/2 = 1.0, 1/2 = 0.5).
    """

    def test_observation_shape(self):
        """The observation must be a 1D array of exactly 205 elements
        (40 cells * 5 features + 5 scalar features)."""
        env = PushFightEnv()
        obs, info = env.reset()
        assert obs.shape == (205,), f"Expected (205,), got {obs.shape}"

    def test_observation_range(self):
        """All observation values must be normalized to [0, 1] for stable
        neural network training."""
        env = PushFightEnv()
        obs, info = env.reset()
        assert np.all(obs >= 0.0)
        assert np.all(obs <= 1.0)

    def test_observation_scalars_at_reset(self):
        """Verify the 5 scalar features at the end of the observation vector
        have correct initial values after a fresh reset. These scalars encode
        phase, move budget, turn, and round-piece counts."""
        env = PushFightEnv()
        obs, info = env.reset()
        assert obs[200] == 0.0   # is_push_phase — not in push phase
        assert obs[201] == 1.0   # moves_remaining — 2 moves available (2/2)
        assert obs[202] == 1.0   # is_white_turn — white starts
        assert obs[203] == 1.0   # own_rounds — 2 round pieces alive (2/2)
        assert obs[204] == 1.0   # opp_rounds — 2 round pieces alive (2/2)

    def test_observation_is_mine_perspective(self):
        """The is_mine feature (index 1 within each cell's 5-feature block)
        must reflect the current player's perspective. On white's turn,
        white pieces should have is_mine=1.0. This perspective encoding
        allows the same neural network to play both sides."""
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
        """When a round piece is removed from the board (simulating a push-off),
        the opp_rounds scalar (obs[204]) must decrease from 1.0 to 0.5,
        reflecting that only 1 of 2 opponent round pieces remains."""
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
    """Tests for the action_masks() method that returns a boolean mask over
    the full 1800-action space.

    The mask enforces phase-dependent legality: during the move phase only
    move actions (0-1599) may be True; during the push phase only push
    actions (1600-1759) may be True; during setup only placement actions
    (1760-1799) may be True. This prevents the agent from taking
    out-of-phase actions.
    """

    def test_action_masks_shape(self):
        """The mask must have exactly 1800 boolean entries — one per possible
        action in the combined move + push + placement space."""
        env = PushFightEnv()
        env.reset()
        mask = env.action_masks()
        assert mask.shape == (1800,)
        assert mask.dtype == bool

    def test_action_masks_has_valid_actions(self):
        """After reset, at least one action must be valid. A mask of all
        False would indicate a broken environment or impossible game state."""
        env = PushFightEnv()
        env.reset()
        mask = env.action_masks()
        assert np.any(mask), "Should have at least one valid action"

    def test_action_masks_move_phase(self):
        """During move phase, only actions in the move range (0-1599) should
        be marked valid. Push and placement actions must all be False."""
        env = PushFightEnv()
        env.reset()
        assert env.current_phase == 'move'
        mask = env.action_masks()
        assert not np.any(mask[1600:]), "Push/place actions shouldn't be valid during move phase"

    def test_action_masks_push_phase(self):
        """During push phase, only actions in the push range (1600-1759)
        should be valid. Move and placement ranges must all be False."""
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
    """Tests for the setup/placement phase of the RL environment.

    During setup, the agent places 5 pieces per team (10 total) on their
    respective halves of the board. These tests use _setup_env_in_setup_mode()
    to manually enter setup mode and verify:
      - Only placement actions (1760-1799) are valid.
      - Territory constraints (white can't place on black's rows).
      - Kill zones are excluded from valid placements.
      - Each placement step adds exactly one piece to the board.
      - The phase transitions to 'move' after 10 placements.
      - Reward shaping: center placements get higher reward than corners.
      - Current player switches from white to black after white's 5 pieces.
    """

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
    """Tests for taking move actions during the move phase.

    Validates that valid moves produce non-negative reward and correct info
    metadata, while invalid moves (e.g., moving from an empty cell) receive
    a small penalty and are substituted with a fallback action rather than
    crashing the environment.
    """

    def test_valid_move(self):
        """A valid move action should produce non-negative reward, set
        action_type='move' in info, and not terminate the episode."""
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
        """An invalid action (e.g., action 0 with no piece at (0,0)) should
        be caught, substituted with a fallback, and penalized with a small
        negative reward to discourage the policy from selecting masked actions."""
        env = PushFightEnv()
        env.reset()
        # Action 0 is almost certainly invalid during move phase (no piece at 0,0)
        obs, reward, terminated, truncated, info = env.step(0)
        assert reward < 0.01  # Should have -0.05 penalty


# ---------------------------------------------------------------------------
# Step: push phase
# ---------------------------------------------------------------------------

class TestStepPushPhase:
    """Tests for executing push actions during the push phase.

    These tests construct specific board configurations by manually placing
    pieces on a fresh PushFightBoard, then verify push execution (piece
    movement, turn switching), kill-zone termination (game_over + winner),
    and the round-threat reward bonus.
    """

    def test_push_executes_once(self):
        """Critical test: a push action must execute exactly once — the pusher
        moves one cell, the pushed piece moves one cell, and no pieces are
        duplicated or lost. This guards against double-execution bugs."""
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
        """After a successful push, the current player must switch and the
        phase must revert to 'move' for the next player's turn."""
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
        """Pushing an opponent's round piece into a kill zone must terminate
        the episode with reward=1.0 (win) and set game_over=True with the
        pushing player as the winner."""
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
    """Smoke tests that run full episodes with randomly selected valid actions.

    These tests verify that the environment can execute a complete game loop
    without crashing, and that episodes eventually terminate (either by a
    piece being pushed off or by reaching the step limit).
    """

    def test_episode_with_random_valid_actions(self):
        """Run up to 500 steps using only valid actions selected randomly.
        The main goal is crash-resistance — any assertion failure indicates
        a bug in action masking, state transitions, or termination logic."""
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
    """Tests for the max_steps truncation mechanism.

    Episodes that exceed max_steps are truncated (truncated=True) to prevent
    infinite games during training. This is separate from termination
    (terminated=True), which occurs when a piece is pushed off.
    """

    def test_truncation_at_max_steps(self):
        """With max_steps=10, the episode must end (truncated or terminated)
        within 15 attempted steps. This verifies the truncation guard fires
        before the episode runs forever."""
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
    """Tests for the edge case where no valid actions exist.

    This can happen when the current player has no square pieces (so no
    push is possible) and the phase is 'push'. The environment must handle
    this gracefully by terminating with a loss reward.
    """

    def test_empty_valid_actions_terminates(self):
        """When no valid push actions exist (only a round piece on the board
        for the current player), the environment must terminate with
        reward=-1.0 (loss) rather than hanging or crashing."""
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
    """Tests for _decode_action(), which converts a flat integer action index
    into a human-readable (phase, data) tuple.

    Action encoding:
      - Move: action = src_y * 160 + src_x * 40 + dst_y * 4 + dst_x
      - Push: action = 1600 + y * 16 + x * 4 + dir_idx
      - Place: action = 1760 + y * 4 + x
    """

    def test_decode_move_action(self):
        """Decode a move action and verify (src_y, src_x, dst_y, dst_x)."""
        env = PushFightEnv()
        env.reset()
        action = 4 * 160 + 0 * 40 + 3 * 4 + 0
        phase, data = env._decode_action(action)
        assert phase == 'move'
        assert data == (4, 0, 3, 0)

    def test_decode_push_action(self):
        """Decode a push action and verify (y, x, direction_tuple)."""
        env = PushFightEnv()
        env.reset()
        env.current_phase = 'push'
        env.game.moves_made = 2
        action = 1600 + 4 * 16 + 0 * 4 + 1
        phase, data = env._decode_action(action)
        assert phase == 'push'
        assert data == (4, 0, (1, 0))

    def test_decode_setup_action(self):
        """Decode a placement action and verify (y, x) target cell."""
        env = _setup_env_in_setup_mode()
        # Place at row 4, col 2: 1760 + 4*4 + 2 = 1778
        action = 1760 + 4 * 4 + 2
        phase, data = env._decode_action(action)
        assert phase == 'place'
        assert data == (4, 2)

    def test_decode_invalid_returns_none(self):
        """An action index that belongs to a different phase (e.g., a push
        action during move phase) must decode to (None, ...) so the step
        logic can reject it."""
        env = PushFightEnv()
        env.reset()
        # Push action during move phase should return None
        phase, data = env._decode_action(1700)
        assert phase is None


# ---------------------------------------------------------------------------
# Is valid push
# ---------------------------------------------------------------------------

class TestIsValidPush:
    """Tests for the _is_valid_push() predicate used by action masking.

    Validates the five conditions that make a push invalid:
      - Pushing from an empty cell.
      - Pushing with a round piece (only squares can push).
      - Pushing with an opponent's piece.
      - Pushing into a side rail (out of bounds).
    And the positive case where all conditions are met.
    """

    def _env_with_pieces(self):
        """Helper: return an env with the standard starting layout forced
        into push phase (moves_made=2). The standard layout has white
        squares at rows 3-4 and black squares at rows 5-6."""
        env = PushFightEnv()
        env.reset()
        env.current_phase = 'push'
        env.game.moves_made = 2
        return env

    def test_valid_push(self):
        """White square at (4,0) pushing down (1,0) — valid because it is
        the current player's square piece pushing into a playable direction."""
        env = self._env_with_pieces()
        assert env._is_valid_push(4, 0, (1, 0)) is True

    def test_invalid_push_empty_square(self):
        """Pushing from an empty cell (3,0) must be invalid — there is no
        piece to initiate the push."""
        env = self._env_with_pieces()
        assert env._is_valid_push(3, 0, (1, 0)) is False

    def test_invalid_push_round_piece(self):
        """Round pieces cannot push. White round at (4,3) must be rejected."""
        env = self._env_with_pieces()
        assert env._is_valid_push(4, 3, (1, 0)) is False

    def test_invalid_push_opponent_piece(self):
        """Cannot push with the opponent's piece. Black square at (5,0) on
        white's turn must be rejected."""
        env = self._env_with_pieces()
        assert env._is_valid_push(5, 0, (1, 0)) is False

    def test_invalid_push_side_rail(self):
        """Pushing into a side rail (column -1) must be rejected — side rails
        block pushes entirely, unlike kill zones which eliminate pieces."""
        env = self._env_with_pieces()
        assert env._is_valid_push(4, 0, (0, -1)) is False
