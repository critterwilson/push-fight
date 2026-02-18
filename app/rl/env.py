"""Gymnasium environment for Push Fight game."""

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from app.engine.game_state import GameState


class PushFightEnv(gym.Env):
    """
    Gymnasium environment for Push Fight game.

    Observation space: Flattened 10x4x5 array + 3 scalars = 203 features
    - Per-cell features (10x4x5=200): [has_piece, is_mine, is_square, is_anchor, is_kill_zone]
    - Scalar features (3): [current_phase, moves_remaining, is_white_turn]

    Action space: Discrete(1760)
    - Move actions (0-1599): piece_y * 160 + piece_x * 40 + dest_y * 4 + dest_x
    - Push actions (1600-1759): 1600 + piece_y * 16 + piece_x * 4 + direction_idx
    """

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}

    def __init__(self, render_mode=None, flatten_obs=True, suppress_prints=True):
        super().__init__()

        self.render_mode = render_mode
        self.flatten_obs = flatten_obs
        self.suppress_prints = suppress_prints
        self.game = None

        # Observation: 200 board features + 3 scalar features = 203
        if flatten_obs:
            self.observation_space = spaces.Box(
                low=0, high=1, shape=(203,), dtype=np.float32
            )
        else:
            # When not flattened, return dict-style would be better but
            # keep simple Box for compatibility; just flatten always.
            self.observation_space = spaces.Box(
                low=0, high=1, shape=(203,), dtype=np.float32
            )

        # Action space: 1600 move actions + 160 push actions = 1760
        self.action_space = spaces.Discrete(1760)

        self.current_phase = 'move'
        self.max_steps = 300  # Episode length limit
        self.step_count = 0

    def _get_observation(self):
        """Convert game state to observation array (203 features)."""
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
                    # Feature 1: is_mine (from current player's perspective)
                    obs[y, x, 1] = 1.0 if piece.team == current_player else 0.0
                    obs[y, x, 2] = 1.0 if piece.shape == 'square' else 0.0  # is_square
                    # Feature 3: is_anchor
                    if self.game.board.anchor_pos[0] is not None:
                        if (y, x) == self.game.board.anchor_pos:
                            obs[y, x, 3] = 1.0

        flat_board = obs.flatten()  # 200 features

        # Scalar features
        is_push_phase = 1.0 if self.current_phase == 'push' else 0.0
        moves_remaining = (2 - self.game.moves_made) / 2.0  # Normalized 0-1
        is_white_turn = 1.0 if current_player == 'white' else 0.0

        return np.concatenate([flat_board, [is_push_phase, moves_remaining, is_white_turn]]).astype(np.float32)

    def _decode_action(self, action):
        """Decode flat action integer into move or push action."""
        if self.current_phase == 'move' and self.game.can_move():
            if action < 1600:
                piece_y = action // (4 * 10 * 4)
                remainder = action % (4 * 10 * 4)
                piece_x = remainder // (10 * 4)
                remainder = remainder % (10 * 4)
                dest_y = remainder // 4
                dest_x = remainder % 4
                return ('move', (piece_y, piece_x, dest_y, dest_x))
            else:
                return (None, None)
        else:
            push_action = action - 1600
            if 0 <= push_action < 160:
                piece_y = push_action // (4 * 4)
                remainder = push_action % (4 * 4)
                piece_x = remainder // 4
                direction_idx = remainder % 4
                directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                direction = directions[direction_idx]
                return ('push', (piece_y, piece_x, direction))
            else:
                return (None, None)

    def _min_kill_zone_distance(self, team):
        """Minimum distance from any piece of `team` to the nearest kill zone row.
        Lower = closer to danger. Used for reward shaping."""
        min_dist = 10
        for y in range(10):
            for x in range(4):
                piece = self.game.board.get_piece(y, x)
                if piece and piece != "OUT_OF_BOUNDS" and piece.team == team:
                    # Distance to nearest kill zone row (0 or 9)
                    dist = min(y, 9 - y)
                    if dist < min_dist:
                        min_dist = dist
        return min_dist

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
        valid_mask = np.zeros(1760, dtype=bool)
        for action in self._get_valid_actions():
            if 0 <= action < 1760:
                valid_mask[action] = True
        return valid_mask

    def action_masks(self):
        """Public API for MaskablePPO action masking."""
        return self._get_valid_actions_mask()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

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
            # Current player has no moves -> they lose
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
        if phase == 'move':
            piece_y, piece_x, dest_y, dest_x = action_data
            piece = self.game.board.get_piece(piece_y, piece_x)

            self.game.board.pieces[piece_y][piece_x] = None
            self.game.board.pieces[dest_y][dest_x] = piece
            self.game.moves_made += 1

            if not self.game.can_move():
                self.current_phase = 'push'

            # No micro-reward for moves — let win/loss dominate
            info['action_type'] = 'move'

        elif phase == 'push':
            piece_y, piece_x, direction = action_data

            # Snapshot opponent piece positions before push for reward shaping
            opponent = 'black' if self.game.current_player == 'white' else 'white'
            opp_dist_before = self._min_kill_zone_distance(opponent)

            # Execute push ONCE (fix for bug 2.1 - was being called twice)
            success = self.game.perform_push(piece_y, piece_x, direction)

            if not success:
                # Should not happen since we validated above, but handle gracefully
                reward = -0.5
                info['action_type'] = 'invalid_push'
                observation = self._get_observation()
                return observation, reward, terminated, truncated, info

            # Check for game over after push
            self.game.check_game_over()

            if self.game.game_over:
                terminated = True
                # Reward from the perspective of the player who just pushed
                if self.game.winner == self.game.current_player:
                    reward = 1.0
                else:
                    reward = -1.0
            else:
                # Small shaping reward: did we push opponent pieces closer to kill zones?
                opp_dist_after = self._min_kill_zone_distance(opponent)
                if opp_dist_after < opp_dist_before:
                    reward += 0.05  # Pushed opponent closer to danger

                # Switch turns
                self.game.switch_turn()
                self.current_phase = 'move'

                # Check if opponent is trapped (no legal pushes available)
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
                status = f"{self.game.current_player.upper()} | {self.current_phase.upper()} | Moves: {self.game.moves_made}/2"
                if self.game.game_over:
                    status += f" | WINNER: {self.game.winner.upper()}"
                print("\u2502" + status.ljust(30) + "\u2502")
                print("\u2514" + "\u2500" * 30 + "\u2518")
        elif self.render_mode == "rgb_array":
            return np.zeros((400, 300, 3), dtype=np.uint8)

        return None

    def close(self):
        pass
