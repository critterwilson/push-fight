"""Gymnasium environment for Push Fight game."""

import os
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from app.engine.game_state import GameState


# Piece placement order: sleeve, lapel, belt (squares), neck, joint (rounds)
PIECE_ROSTER = [
    ('sleeve', 'square'), ('lapel', 'square'), ('belt', 'square'),
    ('neck', 'round'), ('joint', 'round'),
]

# Scale for per-step edge-proximity reward shaping.
EDGE_REWARD_SCALE = 0.02

# One-time bonus per opponent round piece found at edge_dist ≤ 1 after a push.
# Round pieces are instant-loss targets; this rewards setting them up to be knocked off.
ROUND_THREAT_REWARD = 0.1


def _edge_dist(row, col):
    """Distance (in push steps) from (row, col) to the nearest board boundary.

    A piece at distance 0 (e.g. row 0 or 9, or col 0 or 3) falls off the board
    in a single push; lower distance = higher danger/opportunity.
    """
    return min(row, 9 - row, col, 3 - col)


class PushFightEnv(gym.Env):
    """
    Gymnasium environment for Push Fight game.

    Observation space: Flattened 10x4x5 array + 5 scalars = 205 features
    - Per-cell features (10x4x5=200): [has_piece, is_mine, is_square, is_anchor, is_kill_zone]
    - Scalar features (5):
        [is_push_phase, moves_remaining, is_white_turn, is_setup_phase, pieces_placed_fraction]

    Action space: Discrete(1800)
    - Move actions      (0–1599):    piece_y * 160 + piece_x * 40 + dest_y * 4 + dest_x
    - Push actions      (1600–1759): 1600 + piece_y * 16 + piece_x * 4 + direction_idx
    - Placement actions (1760–1799): 1760 + y * 4 + x  (places next piece in roster at cell)
    """

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}

    def __init__(self, render_mode=None, flatten_obs=True, suppress_prints=True):
        super().__init__()

        self.render_mode = render_mode
        self.flatten_obs = flatten_obs
        self.suppress_prints = suppress_prints
        self.game = None

        # Observation: 200 board features + 5 scalar features = 205
        self.observation_space = spaces.Box(
            low=0, high=1, shape=(205,), dtype=np.float32
        )

        # Action space: 1600 move + 160 push + 40 placement = 1800
        self.action_space = spaces.Discrete(1800)

        self.current_phase = 'setup'
        self.max_steps = 300  # Episode length limit
        self.step_count = 0

    # -------------------------------------------------------------------------
    # Observation
    # -------------------------------------------------------------------------

    def _get_observation(self):
        """Convert game state to observation array (205 features)."""
        obs = np.zeros((10, 4, 5), dtype=np.float32)
        current_player = self.game.current_player

        for y in range(10):
            for x in range(4):
                # Feature 4: is_kill_zone
                if self.game.board.grid[y][x] == -1:
                    obs[y, x, 4] = 1.0

                piece = self.game.board.get_piece(y, x)
                if piece and piece != "OUT_OF_BOUNDS":
                    obs[y, x, 0] = 1.0  # has_piece
                    obs[y, x, 1] = 1.0 if piece.team == current_player else 0.0  # is_mine
                    obs[y, x, 2] = 1.0 if piece.shape == 'square' else 0.0  # is_square
                    if self.game.board.anchor_pos[0] is not None:
                        if (y, x) == self.game.board.anchor_pos:
                            obs[y, x, 3] = 1.0  # is_anchor

        flat_board = obs.flatten()  # 200 features

        # Scalar features
        is_push_phase = 1.0 if self.current_phase == 'push' else 0.0
        moves_remaining = (2 - self.game.moves_made) / 2.0
        is_white_turn = 1.0 if current_player == 'white' else 0.0

        # Round piece survival (0.0, 0.5, or 1.0 each).  Losing a round piece is an
        # instant loss, so these are the most win-condition-relevant scalars.
        opponent = 'black' if current_player == 'white' else 'white'
        own_rounds = self.game.count_round_pieces(current_player) / 2.0
        opp_rounds = self.game.count_round_pieces(opponent) / 2.0

        return np.concatenate([
            flat_board,
            [is_push_phase, moves_remaining, is_white_turn, own_rounds, opp_rounds],
        ]).astype(np.float32)

    # -------------------------------------------------------------------------
    # Action helpers
    # -------------------------------------------------------------------------

    def _decode_action(self, action):
        """Decode flat action integer into (phase_type, data) or (None, None)."""
        if self.current_phase == 'setup':
            idx = action - 1760
            if 0 <= idx < 40:
                return ('place', (idx // 4, idx % 4))
            return (None, None)

        if self.current_phase == 'move' and self.game.can_move():
            if action < 1600:
                piece_y = action // (4 * 10 * 4)
                remainder = action % (4 * 10 * 4)
                piece_x = remainder // (10 * 4)
                remainder = remainder % (10 * 4)
                dest_y = remainder // 4
                dest_x = remainder % 4
                return ('move', (piece_y, piece_x, dest_y, dest_x))
            return (None, None)

        # Push phase
        push_action = action - 1600
        if 0 <= push_action < 160:
            piece_y = push_action // (4 * 4)
            remainder = push_action % (4 * 4)
            piece_x = remainder // 4
            direction_idx = remainder % 4
            directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            direction = directions[direction_idx]
            return ('push', (piece_y, piece_x, direction))
        return (None, None)

    def _get_next_piece(self, team):
        """Return (name, shape) for the next unplaced piece in PIECE_ROSTER, or None."""
        placed_names = {
            self.game.board.get_piece(y, x).name
            for y in range(10) for x in range(4)
            if self.game.board.get_piece(y, x) and
               self.game.board.get_piece(y, x) != "OUT_OF_BOUNDS" and
               self.game.board.get_piece(y, x).team == team
        }
        for name, shape in PIECE_ROSTER:
            if name not in placed_names:
                return (name, shape)
        return None

    def _is_valid_placement(self, y, x):
        """Check if cell is a valid placement for the current player's next piece."""
        team = self.game.current_player

        if not self.game._is_on_player_side(y, team):
            return False
        if not self.game._is_playable_space(y, x):
            return False
        if self.game.board.is_occupied(y, x):
            return False
        if self._get_next_piece(team) is None:
            return False  # All pieces already placed

        return True

    def _min_kill_zone_distance(self, team):
        """Minimum distance from any piece of `team` to the nearest kill zone row."""
        min_dist = 10
        for y in range(10):
            for x in range(4):
                piece = self.game.board.get_piece(y, x)
                if piece and piece != "OUT_OF_BOUNDS" and piece.team == team:
                    dist = min(y, 9 - y)
                    if dist < min_dist:
                        min_dist = dist
        return min_dist

    def _edge_proximity_reward(self):
        """Per-step reward based on piece proximity to board edges.

        Opponent pieces near the edge = positive (push-off opportunity).
        Own pieces near the edge = negative (vulnerability).
        Round pieces (neck, joint) are weighted 2× square pieces because they
        cannot form walls and are prime push-off targets.
        """
        current = self.game.current_player
        opponent = 'black' if current == 'white' else 'white'
        reward = 0.0
        for y in range(10):
            for x in range(4):
                if self.game.board.grid[y][x] == -1:
                    continue
                piece = self.game.board.get_piece(y, x)
                if not piece or piece == "OUT_OF_BOUNDS":
                    continue
                ed = _edge_dist(y, x)
                weight = 1.0 if piece.shape == 'round' else 0.5
                proximity = EDGE_REWARD_SCALE * weight / (ed + 1)
                if piece.team == opponent:
                    reward += proximity   # Opponent vulnerable → good
                else:
                    reward -= proximity   # Own pieces vulnerable → bad
        return reward

    def _is_valid_push(self, piece_y, piece_x, direction):
        """Check if a push is valid WITHOUT executing it."""
        piece = self.game.board.get_piece(piece_y, piece_x)
        if not piece or piece == "OUT_OF_BOUNDS":
            return False
        if piece.shape != 'square':
            return False
        if piece.team != self.game.current_player:
            return False

        dy, dx = direction
        chain, landing_spot = self.game.board.get_push_chain(piece_y, piece_x, dy, dx)

        # Side rail blocks
        if not self.game.board.is_on_board(*landing_spot):
            return False

        return True

    def _get_valid_actions(self):
        """Get list of valid action indices for current state."""
        valid_actions = []

        if self.current_phase == 'setup':
            for y in range(10):
                for x in range(4):
                    if self._is_valid_placement(y, x):
                        valid_actions.append(1760 + y * 4 + x)
            return valid_actions

        if self.current_phase == 'move' and self.game.can_move():
            for y in range(10):
                for x in range(4):
                    piece = self.game.board.get_piece(y, x)
                    if (piece and piece != "OUT_OF_BOUNDS" and
                            piece.team == self.game.current_player):
                        valid_moves = self.game.board.get_valid_moves(y, x)
                        for dest_y, dest_x in valid_moves:
                            action = y * (4 * 10 * 4) + x * (10 * 4) + dest_y * 4 + dest_x
                            if 0 <= action < 1600:
                                valid_actions.append(action)
        else:
            for y in range(10):
                for x in range(4):
                    piece = self.game.board.get_piece(y, x)
                    if (piece and piece != "OUT_OF_BOUNDS" and
                            piece.team == self.game.current_player and
                            piece.shape == 'square'):
                        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                        for dir_idx, direction in enumerate(directions):
                            if self._is_valid_push(y, x, direction):
                                action = 1600 + y * (4 * 4) + x * 4 + dir_idx
                                if 1600 <= action < 1760:
                                    valid_actions.append(action)

        return valid_actions

    def _get_valid_actions_mask(self):
        """Get boolean mask of valid actions (for MaskablePPO)."""
        valid_mask = np.zeros(1800, dtype=bool)
        for action in self._get_valid_actions():
            if 0 <= action < 1800:
                valid_mask[action] = True
        return valid_mask

    def action_masks(self):
        """Public API for MaskablePPO action masking."""
        return self._get_valid_actions_mask()

    # -------------------------------------------------------------------------
    # Gymnasium API
    # -------------------------------------------------------------------------

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        # Use the fixed standard starting position so training focuses entirely on
        # gameplay, not piece placement.  The server handles setup separately via
        # _auto_place(); agent.get_action() returns None during setup mode anyway.
        self.game = GameState.create_initial_game()
        self.current_phase = 'move'
        self.step_count = 0

        observation = self._get_observation()
        info = {
            'current_player': self.game.current_player,
            'phase': self.current_phase,
            'moves_made': self.game.moves_made,
            'valid_actions': len(self._get_valid_actions()),
        }

        return observation, info

    def step(self, action):
        """Execute one step in the environment."""
        reward = 0.0
        terminated = False
        truncated = False
        info = {}
        self.step_count += 1

        # Truncate long episodes
        if self.step_count >= self.max_steps:
            truncated = True
            observation = self._get_observation()
            info['action_type'] = 'truncated'
            return observation, 0.0, terminated, truncated, info

        valid_list = self._get_valid_actions()

        # If no valid actions, the game should be over
        if not valid_list:
            terminated = True
            self.game.game_over = True
            opponent = 'black' if self.game.current_player == 'white' else 'white'
            self.game.winner = opponent
            reward = -1.0
            observation = self._get_observation()
            info['action_type'] = 'no_valid_actions'
            return observation, reward, terminated, truncated, info

        # Decode the action
        phase, action_data = self._decode_action(action)

        # Check if the action is valid; if not, pick a random valid one
        substituted = False
        if phase is None:
            substituted = True
        elif phase == 'place':
            y, x = action_data
            if not self._is_valid_placement(y, x):
                substituted = True
        elif phase == 'move':
            piece_y, piece_x, dest_y, dest_x = action_data
            piece = self.game.board.get_piece(piece_y, piece_x)
            if (not piece or piece == "OUT_OF_BOUNDS" or
                    piece.team != self.game.current_player):
                substituted = True
            else:
                valid_moves = self.game.board.get_valid_moves(piece_y, piece_x)
                if (dest_y, dest_x) not in valid_moves:
                    substituted = True
        elif phase == 'push':
            piece_y, piece_x, direction = action_data
            if not self._is_valid_push(piece_y, piece_x, direction):
                substituted = True

        if substituted:
            action = int(self.np_random.choice(valid_list))
            phase, action_data = self._decode_action(action)
            reward -= 0.05  # Small penalty; action masking should make this rare

        # Execute the action
        if phase == 'place':
            y, x = action_data
            team = self.game.current_player
            next_piece = self._get_next_piece(team)
            if next_piece:
                name, shape = next_piece
                success, _ = self.game.place_piece(y, x, team, shape, name)
                if success:
                    # Reward: base + centrality + near-midline bonus
                    reward += 0.001
                    if x in (1, 2):
                        reward += 0.002
                    if (team == 'white' and y in (3, 4)) or (team == 'black' and y in (5, 6)):
                        reward += 0.002

                    # Check if current team's setup is complete
                    status = self.game.get_placement_status(team)
                    if status['squares'] == 3 and status['rounds'] == 2:
                        opponent = 'black' if team == 'white' else 'white'
                        opp_status = self.game.get_placement_status(opponent)
                        if opp_status['squares'] == 3 and opp_status['rounds'] == 2:
                            # Both teams done — start game
                            self.game.start_game()
                            self.current_phase = 'move'
                        else:
                            # Switch to opponent's setup turn
                            self.game.current_player = opponent

            info['action_type'] = 'place'

        elif phase == 'move':
            piece_y, piece_x, dest_y, dest_x = action_data
            piece = self.game.board.get_piece(piece_y, piece_x)

            self.game.board.pieces[piece_y][piece_x] = None
            self.game.board.pieces[dest_y][dest_x] = piece
            self.game.moves_made += 1

            if not self.game.can_move():
                self.current_phase = 'push'

            # Positional reward: reward moving to better positions
            reward += self._edge_proximity_reward()

            info['action_type'] = 'move'

        elif phase == 'push':
            piece_y, piece_x, direction = action_data

            # Snapshot opponent distances for reward shaping
            opponent = 'black' if self.game.current_player == 'white' else 'white'
            opp_dist_before = self._min_kill_zone_distance(opponent)

            success = self.game.perform_push(piece_y, piece_x, direction)

            if not success:
                reward = -0.5
                info['action_type'] = 'invalid_push'
                observation = self._get_observation()
                return observation, reward, terminated, truncated, info

            self.game.check_game_over()

            if self.game.game_over:
                terminated = True
                if self.game.winner == self.game.current_player:
                    reward = 1.0
                else:
                    reward = -1.0
            else:
                opp_dist_after = self._min_kill_zone_distance(opponent)
                if opp_dist_after < opp_dist_before:
                    reward += 0.05  # Pushed opponent closer to danger

                # Bonus for each opponent round piece now sitting at edge_dist ≤ 1
                # (one push away from the kill zone — an immediate threat).
                for y in range(10):
                    for x in range(4):
                        piece = self.game.board.get_piece(y, x)
                        if (piece and piece != "OUT_OF_BOUNDS" and
                                piece.team == opponent and piece.shape == 'round' and
                                _edge_dist(y, x) <= 1):
                            reward += ROUND_THREAT_REWARD

                # Edge proximity reward before switching turns (current_player still = pusher)
                reward += self._edge_proximity_reward()

                self.game.switch_turn()
                self.current_phase = 'move'

                if not self.game.has_legal_push():
                    self.game.game_over = True
                    prev_player = 'black' if self.game.current_player == 'white' else 'white'
                    self.game.winner = prev_player
                    terminated = True
                    reward = -1.0

            info['action_type'] = 'push'

        observation = self._get_observation()
        info['current_player'] = self.game.current_player
        info['phase'] = self.current_phase
        info['game_over'] = self.game.game_over
        info['valid_actions'] = len(self._get_valid_actions()) if not terminated else 0

        if 'action_type' not in info:
            info['action_type'] = 'unknown'

        return observation, reward, terminated, truncated, info

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def render(self, clear_screen=True):
        if self.render_mode == "human":
            if self.game:
                if clear_screen:
                    try:
                        print("\033[2J\033[H", end="")
                    except Exception:
                        print("\n" * 3)
                else:
                    print("\n")

                print("\u250c" + "\u2500" * 9 + " PUSH FIGHT " + "\u2500" * 9 + "\u2510")

                header = "   "
                for x in range(4):
                    header += f"  {x} "
                print("\u2502" + header.ljust(30) + "\u2502")
                print("\u251c" + "\u2500" * 30 + "\u2524")

                for y in range(10):
                    row_str = f"{y:2} "
                    for x in range(4):
                        piece = self.game.board.get_piece(y, x)
                        if self.game.board.grid[y][x] == -1:
                            row_str += "XXX "
                        elif piece is None:
                            row_str += "... "
                        elif piece == "OUT_OF_BOUNDS":
                            row_str += "### "
                        else:
                            team_char = "W" if piece.team == 'white' else "B"
                            shape_char = "S" if piece.shape == 'square' else "R"
                            anchor = "*" if (y, x) == self.game.board.anchor_pos else " "
                            row_str += f"{team_char}{shape_char}{anchor} "
                    print("\u2502" + row_str.ljust(30) + "\u2502")

                print("\u251c" + "\u2500" * 30 + "\u2524")
                if self.current_phase == 'setup':
                    w_status = self.game.get_placement_status('white')
                    b_status = self.game.get_placement_status('black')
                    status = (f"{self.game.current_player.upper()} SETUP | "
                              f"W:{w_status['squares']}sq+{w_status['rounds']}rnd "
                              f"B:{b_status['squares']}sq+{b_status['rounds']}rnd")
                else:
                    status = (f"{self.game.current_player.upper()} | "
                              f"{self.current_phase.upper()} | Moves: {self.game.moves_made}/2")
                if self.game.game_over:
                    status += f" | WINNER: {self.game.winner.upper()}"
                print("\u2502" + status.ljust(30) + "\u2502")
                print("\u2514" + "\u2500" * 30 + "\u2518")
        elif self.render_mode == "rgb_array":
            return np.zeros((400, 300, 3), dtype=np.uint8)

        return None

    def close(self):
        pass


class SelfPlayEnv(PushFightEnv):
    """PushFightEnv where the agent plays one fixed color and the opponent auto-plays.

    Each episode the agent's color is chosen randomly (white or black) so the
    policy learns symmetric play.  The opponent is sampled from a snapshot pool
    so both sides improve over time (or fall back to random when the pool is
    empty).

    Training workflow
    -----------------
    1. reset(): pick agent_team randomly, load opponent snapshot from pool.
    2. SelfPlayCallback saves current model to pool every N steps.
    3. Each subsequent reset() samples a (possibly stronger) snapshot.
    4. The policy gradually improves against itself from both sides of the board.
    """

    def __init__(self, pool_dir='models/pool', p_random=0.2, **kwargs):
        super().__init__(**kwargs)
        self.pool_dir = pool_dir
        self.p_random = p_random   # probability opponent plays purely random this episode
        self.opponent_model = None
        self.agent_team = 'white'  # updated each reset()

    # ------------------------------------------------------------------
    # Gymnasium API overrides
    # ------------------------------------------------------------------

    def reset(self, seed=None, options=None):
        # Randomly pick which color the learning agent plays this episode
        self.agent_team = np.random.choice(['white', 'black'])
        self._reload_opponent()
        obs, info = super().reset(seed=seed, options=options)
        # If it's the opponent's turn first, auto-play until agent's turn
        if self.game.current_player != self.agent_team:
            obs, info = self._drain_opponent_turns(obs, info)
        return obs, info

    def step(self, action):
        """Agent takes an action; then opponent auto-plays until agent's turn."""
        obs, reward, terminated, truncated, info = super().step(action)

        if terminated or truncated:
            return obs, reward, terminated, truncated, info

        # Auto-play all opponent turns
        while not terminated and not truncated and self.game.current_player != self.agent_team:
            opp_action = self._get_opponent_action(obs)
            obs, _, terminated, truncated, info = super().step(opp_action)

        # If the game ended during the opponent's turn, translate to agent's POV
        if terminated and self.game.game_over:
            reward = 1.0 if self.game.winner == self.agent_team else -1.0

        return obs, reward, terminated, truncated, info

    # ------------------------------------------------------------------
    # Opponent helpers
    # ------------------------------------------------------------------

    def _get_opponent_action(self, obs):
        """Return an action index for the opponent (model or random)."""
        valid = self._get_valid_actions()
        if not valid:
            return 0

        use_model = (
            self.opponent_model is not None
            and np.random.random() >= self.p_random
        )
        if use_model:
            try:
                masks = self.action_masks()
                action, _ = self.opponent_model.predict(
                    obs, deterministic=True, action_masks=masks
                )
                return int(action)
            except Exception:
                pass  # Fall back to random on any prediction error

        return int(np.random.choice(valid))

    def _reload_opponent(self):
        """Load a snapshot from the pool directory, weighted toward recent ones.

        Uniform sampling would mean the agent spends most episodes against its
        earliest (weakest) self.  Linear weighting toward the most recent snapshot
        ensures the curriculum keeps up with the improving policy.
        """
        if not os.path.isdir(self.pool_dir):
            self.opponent_model = None
            return

        snapshots = [f for f in os.listdir(self.pool_dir) if f.endswith('.zip')]
        if not snapshots or np.random.random() < self.p_random:
            self.opponent_model = None
            return

        # Sort by the step number embedded in the filename (snapshot_NNNNN.zip).
        def _step_num(fname):
            try:
                return int(fname.replace('snapshot_', '').replace('.zip', ''))
            except ValueError:
                return 0

        snapshots_sorted = sorted(snapshots, key=_step_num)
        n = len(snapshots_sorted)
        # Linear weights: oldest gets weight 1, most recent gets weight n.
        weights = np.arange(1, n + 1, dtype=float)
        weights /= weights.sum()
        snapshot = np.random.choice(snapshots_sorted, p=weights)

        path = os.path.join(self.pool_dir, snapshot)
        try:
            from sb3_contrib import MaskablePPO
            # Load without env — used for predict() only
            self.opponent_model = MaskablePPO.load(path, device='cpu')
        except Exception:
            self.opponent_model = None

    def _drain_opponent_turns(self, obs, info):
        """Auto-play opponent turns until it's the agent's turn (used after reset)."""
        while self.game.current_player != self.agent_team and not self.game.game_over:
            action = self._get_opponent_action(obs)
            obs, _, terminated, truncated, info = super().step(action)
            if terminated or truncated:
                break
        return obs, info
