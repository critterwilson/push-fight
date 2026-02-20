"""Gymnasium environment for the Push Fight board game.

This module implements a Gymnasium-compatible environment for training
reinforcement learning agents to play Push Fight using Proximal Policy
Optimization (PPO) with invalid-action masking (MaskablePPO from sb3-contrib).

Push Fight overview
-------------------
Push Fight is a two-player abstract strategy game on a 10x4 board.  Each player
has 5 pieces: 3 square pieces and 2 round pieces.  On each turn a player may
optionally slide up to 2 of their pieces (move phase), then *must* push with
exactly one of their square pieces (push phase).  A push shoves an entire chain
of adjacent pieces one cell in a cardinal direction; if any piece is pushed off
the board edge, that piece's team loses instantly.  After a push, an anchor is
placed on the pushing piece, preventing the opponent from pushing it on their
next turn.

Why MaskablePPO?
----------------
Push Fight has a large discrete action space (1800 actions) but only a small
subset is legal in any given state.  Standard PPO would waste most of its
probability mass on illegal moves and learn slowly.  MaskablePPO (from
sb3-contrib) accepts a boolean mask each step that zeroes out logits for
invalid actions *before* the softmax, so the policy only ever samples legal
moves.  This dramatically speeds up training and eliminates the need for heavy
invalid-action penalties.

Action encoding
---------------
The 1800-action Discrete space is partitioned into three contiguous ranges:

  Actions 0-1599   (1600 total) -- MOVE actions
    Encoded as: piece_y * 160 + piece_x * 40 + dest_y * 4 + dest_x
    Represents sliding a piece from (piece_y, piece_x) to (dest_y, dest_x).

  Actions 1600-1759 (160 total) -- PUSH actions
    Encoded as: 1600 + piece_y * 16 + piece_x * 4 + direction_idx
    direction_idx: 0=up(-1,0), 1=down(+1,0), 2=left(0,-1), 3=right(0,+1)
    Represents pushing with a square piece at (piece_y, piece_x).

  Actions 1760-1799 (40 total)  -- PLACEMENT actions (setup phase only)
    Encoded as: 1760 + y * 4 + x
    Places the next unplaced piece from PIECE_ROSTER at cell (y, x).

Observation space
-----------------
A flat 205-element float32 vector:
  - 200 board features: 10 rows x 4 cols x 5 per-cell channels
      [0] has_piece      -- 1.0 if a piece occupies this cell
      [1] is_mine        -- 1.0 if the piece belongs to the current player
      [2] is_square      -- 1.0 if the piece is square (can push / receive anchor)
      [3] is_anchor      -- 1.0 if the anchor marker is on this cell
      [4] is_kill_zone   -- 1.0 if this cell is a board-edge hazard zone
  - 5 scalar features appended after the flattened board:
      [200] is_push_phase          -- 1.0 during push phase, 0.0 otherwise
      [201] moves_remaining        -- fraction of optional moves left (0..1)
      [202] is_white_turn          -- 1.0 if white is the current player
      [203] own_round_pieces_frac  -- fraction of own round pieces surviving
      [204] opp_round_pieces_frac  -- fraction of opponent round pieces surviving

Reward design
-------------
  +1.0  / -1.0   Terminal win / loss.
  -0.05          Penalty when the model's chosen action was invalid and had
                 to be substituted (should be rare with proper action masking).
  +EDGE_REWARD_SCALE-based shaping for opponent pieces near edges (positive)
    and own pieces near edges (negative), computed after every move and push.
  +0.05          Bonus when a push moves an opponent piece closer to the
                 kill zone (measured by min-distance decrease).
  +ROUND_THREAT_REWARD  per opponent round piece at edge_dist <= 1 after a
                 push, rewarding the creation of immediate push-off threats.

Classes
-------
  PushFightEnv  -- Base Gymnasium environment (both sides controlled by step()).
  SelfPlayEnv   -- Extends PushFightEnv; the learning agent plays one color
                   while an opponent auto-plays from a pool of saved snapshots.
"""

import os
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from app.engine.game_state import GameState


# Piece placement order used during the setup phase.
# Squares are placed first (they can push and receive anchors), then rounds
# (which are prime push-off targets and cannot push).
PIECE_ROSTER = [
    ('sleeve', 'square'), ('lapel', 'square'), ('belt', 'square'),
    ('neck', 'round'), ('joint', 'round'),
]

# Multiplicative scale for the per-step edge-proximity reward shaping signal.
# Kept small relative to the +/-1.0 terminal reward so shaping guides
# exploration without overwhelming the true win/loss objective.
EDGE_REWARD_SCALE = 0.02

# One-time bonus awarded for each opponent round piece that ends up within
# one cell of the board edge after the agent's push.  Round pieces are
# instant-loss targets (pushing one off ends the game), so threatening them
# is strategically valuable and worth explicitly rewarding.
ROUND_THREAT_REWARD = 0.1


def _edge_dist(row, col):
    """Compute the minimum number of push steps to reach the nearest board edge.

    The board is 10 rows by 4 columns (indices 0-9 and 0-3).  A piece at
    distance 0 is already on the boundary and can be pushed off in a single
    push.  Lower distance means higher danger for the piece's owner and
    higher opportunity for the opponent.

    Args:
        row: Row index (0-9) on the board.
        col: Column index (0-3) on the board.

    Returns:
        int: Manhattan distance to the nearest edge (0 = on the edge).
    """
    return min(row, 9 - row, col, 3 - col)


class PushFightEnv(gym.Env):
    """Base Gymnasium environment for the Push Fight board game.

    This environment models both players' actions through a single ``step()``
    call.  For self-play training, ``SelfPlayEnv`` wraps this class and
    auto-plays one side using a snapshot model.

    The observation is always encoded from the *current* player's perspective:
    ``is_mine`` is 1.0 for the current player's pieces regardless of which
    color they are.  This means the policy learns a single strategy that works
    for either side of the board.

    Design decisions:
      - Flat observation (205 floats) rather than an image -- the board is
        small enough (10x4) that spatial convolutions add complexity without
        clear benefit.  A flat MLP with layers [256, 256, 128] handles this
        well.
      - Discrete(1800) action space covers all possible (piece, destination)
        and (piece, direction) pairs.  Most are invalid in any given state, but
        the action mask ensures the policy never samples them.
      - Phase tracking (setup / move / push) is maintained internally so the
        action mask automatically restricts actions to the correct range for
        the current phase.
      - Episodes are capped at ``max_steps`` (default 300) to prevent infinite
        games during early training when the policy is random.

    Attributes:
        game: The underlying ``GameState`` instance.
        current_phase: One of 'setup', 'move', or 'push'.
        max_steps: Maximum environment steps before truncation.
        step_count: Steps taken in the current episode.
    """

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}

    def __init__(self, render_mode=None, flatten_obs=True, suppress_prints=True):
        """Initialize the Push Fight environment.

        Args:
            render_mode: Gymnasium render mode.  "human" prints the board to
                stdout; "rgb_array" returns a placeholder numpy array.
            flatten_obs: Whether to flatten the observation to 1-D (always True
                for MLP policies; kept as a parameter for future CNN support).
            suppress_prints: If True, suppresses verbose game-engine output
                during step execution.
        """
        super().__init__()

        self.render_mode = render_mode
        self.flatten_obs = flatten_obs
        self.suppress_prints = suppress_prints
        self.game = None

        # Observation: 10 rows * 4 cols * 5 channels = 200 board features
        #            + 5 scalar features = 205 total
        self.observation_space = spaces.Box(
            low=0, high=1, shape=(205,), dtype=np.float32
        )

        # Action space: 1600 move + 160 push + 40 placement = 1800
        # (see module docstring for the full encoding scheme)
        self.action_space = spaces.Discrete(1800)

        self.current_phase = 'setup'
        self.max_steps = 300  # Episode length limit to prevent infinite games
        self.step_count = 0

    # -------------------------------------------------------------------------
    # Observation
    # -------------------------------------------------------------------------

    def _get_observation(self):
        """Convert the current game state into a 205-element observation vector.

        The observation is encoded from the perspective of ``self.game.current_player``:
        the ``is_mine`` channel is 1.0 for that player's pieces.  This means a
        single policy network can play as either white or black without needing
        to know its color explicitly.

        Returns:
            np.ndarray: Float32 array of shape (205,).
        """
        # Board tensor: 10 rows x 4 cols x 5 feature channels, initialized to zero.
        obs = np.zeros((10, 4, 5), dtype=np.float32)
        current_player = self.game.current_player

        for y in range(10):
            for x in range(4):
                # Channel 4: is_kill_zone -- cells marked -1 in the grid are
                # hazard zones at the board edges where pieces can fall off.
                if self.game.board.grid[y][x] == -1:
                    obs[y, x, 4] = 1.0

                piece = self.game.board.get_piece(y, x)
                if piece and piece != "OUT_OF_BOUNDS":
                    obs[y, x, 0] = 1.0  # Channel 0: has_piece
                    obs[y, x, 1] = 1.0 if piece.team == current_player else 0.0  # Channel 1: is_mine
                    obs[y, x, 2] = 1.0 if piece.shape == 'square' else 0.0  # Channel 2: is_square
                    # Channel 3: is_anchor -- the anchor prevents the opponent
                    # from pushing this piece on the next turn.
                    if self.game.board.anchor_pos[0] is not None:
                        if (y, x) == self.game.board.anchor_pos:
                            obs[y, x, 3] = 1.0

        flat_board = obs.flatten()  # 200 features

        # Scalar features that don't map naturally to board cells.
        is_push_phase = 1.0 if self.current_phase == 'push' else 0.0
        # Normalize moves_remaining to [0, 1]: 2 moves left = 1.0, 0 left = 0.0.
        moves_remaining = (2 - self.game.moves_made) / 2.0
        is_white_turn = 1.0 if current_player == 'white' else 0.0

        # Round piece survival fractions (0.0, 0.5, or 1.0 each).
        # Losing a round piece is an instant loss, so these are the most
        # win-condition-relevant scalars in the observation.
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
        """Decode a flat action integer into a (phase_type, data) tuple.

        The decoding depends on the current phase of the game:
          - 'setup': expects actions in [1760, 1800) -> ('place', (y, x))
          - 'move':  expects actions in [0, 1600) -> ('move', (py, px, dy, dx))
          - 'push':  expects actions in [1600, 1760) -> ('push', (py, px, (dy,dx)))

        Args:
            action: Integer in [0, 1800).

        Returns:
            tuple: (phase_type, action_data) where phase_type is 'place',
                'move', or 'push'; or (None, None) if the action doesn't
                correspond to a valid encoding for the current phase.
        """
        if self.current_phase == 'setup':
            # Placement actions occupy indices 1760-1799.
            idx = action - 1760
            if 0 <= idx < 40:
                # Decode cell coordinates: idx = y * 4 + x
                return ('place', (idx // 4, idx % 4))
            return (None, None)

        if self.current_phase == 'move' and self.game.can_move():
            if action < 1600:
                # Move encoding: piece_y * (4*10*4) + piece_x * (10*4) + dest_y * 4 + dest_x
                # This packs source (y,x) and destination (y,x) into a single int.
                piece_y = action // (4 * 10 * 4)
                remainder = action % (4 * 10 * 4)
                piece_x = remainder // (10 * 4)
                remainder = remainder % (10 * 4)
                dest_y = remainder // 4
                dest_x = remainder % 4
                return ('move', (piece_y, piece_x, dest_y, dest_x))
            return (None, None)

        # Push phase: actions 1600-1759
        push_action = action - 1600
        if 0 <= push_action < 160:
            # Push encoding: piece_y * (4*4) + piece_x * 4 + direction_idx
            piece_y = push_action // (4 * 4)
            remainder = push_action % (4 * 4)
            piece_x = remainder // 4
            direction_idx = remainder % 4
            # Cardinal directions: up, down, left, right
            directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            direction = directions[direction_idx]
            return ('push', (piece_y, piece_x, direction))
        return (None, None)

    def _get_next_piece(self, team):
        """Return the next unplaced piece for a team during the setup phase.

        Iterates through PIECE_ROSTER in order (squares first, then rounds)
        and returns the first piece whose name hasn't been placed on the board
        yet for the given team.

        Args:
            team: 'white' or 'black'.

        Returns:
            tuple: (name, shape) for the next piece to place, e.g.
                ('sleeve', 'square'), or None if all 5 pieces are placed.
        """
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
        """Check if cell (y, x) is a valid placement for the current player's next piece.

        A placement is valid if:
          1. The cell is on the current player's half of the board.
          2. The cell is a playable space (not out of bounds or a wall).
          3. The cell is not already occupied.
          4. The player still has pieces left to place.

        Args:
            y: Row index (0-9).
            x: Column index (0-3).

        Returns:
            bool: True if the placement is legal.
        """
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
        """Find the minimum distance from any of a team's pieces to the nearest kill zone.

        Used for reward shaping: when a push decreases this value for the
        opponent, the agent receives a small bonus for creating danger.

        Args:
            team: 'white' or 'black'.

        Returns:
            int: Minimum row-distance to a kill zone row (0 or 9), across
                all pieces belonging to the specified team.  Returns 10 if
                the team has no pieces on the board.
        """
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
        """Compute a per-step reward signal based on piece proximity to board edges.

        The idea is to shape the policy toward pushing opponent pieces to the
        edge (where they can be knocked off) and keeping its own pieces away
        from the edge (where they are vulnerable).

        Reward structure per piece:
          - Opponent pieces near the edge contribute *positive* reward
            (opportunity to push them off).
          - Own pieces near the edge contribute *negative* reward
            (vulnerability to being pushed off).
          - Round pieces are weighted 2x square pieces because they cannot
            form walls and are the primary push-off targets (losing a round
            piece is an instant loss).

        The magnitude is controlled by EDGE_REWARD_SCALE and inversely
        proportional to (edge_distance + 1), so pieces right on the edge
        produce the strongest signal.

        Returns:
            float: Net edge-proximity reward for the current board state.
        """
        current = self.game.current_player
        opponent = 'black' if current == 'white' else 'white'
        reward = 0.0
        for y in range(10):
            for x in range(4):
                # Skip kill-zone cells (they have no piece, just the hazard marker).
                if self.game.board.grid[y][x] == -1:
                    continue
                piece = self.game.board.get_piece(y, x)
                if not piece or piece == "OUT_OF_BOUNDS":
                    continue
                ed = _edge_dist(y, x)
                # Round pieces (weight=1.0) are more important than squares (weight=0.5)
                # because losing a round piece is an instant loss condition.
                weight = 1.0 if piece.shape == 'round' else 0.5
                proximity = EDGE_REWARD_SCALE * weight / (ed + 1)
                if piece.team == opponent:
                    reward += proximity   # Opponent piece near edge = good for us
                else:
                    reward -= proximity   # Our piece near edge = bad for us
        return reward

    def _is_valid_push(self, piece_y, piece_x, direction):
        """Check if a push is valid WITHOUT executing it on the game state.

        A push is valid if:
          1. There is a square piece belonging to the current player at (piece_y, piece_x).
          2. The push chain's landing spot is on the board (not blocked by a side rail).
        Note: being pushed off the top/bottom edge is valid (it ends the game);
        only side-rail blocks make a push invalid.

        Args:
            piece_y: Row of the pushing piece.
            piece_x: Column of the pushing piece.
            direction: Tuple (dy, dx) for the push direction.

        Returns:
            bool: True if the push can legally be executed.
        """
        piece = self.game.board.get_piece(piece_y, piece_x)
        if not piece or piece == "OUT_OF_BOUNDS":
            return False
        if piece.shape != 'square':
            return False  # Only square pieces can push
        if piece.team != self.game.current_player:
            return False  # Can only push with your own pieces

        dy, dx = direction
        chain, landing_spot = self.game.board.get_push_chain(piece_y, piece_x, dy, dx)

        # A push is invalid only if it would go into a side rail (off-board
        # laterally).  Pushing off the top/bottom edge is legal -- it causes
        # a piece to fall off, which is the win condition.
        if not self.game.board.is_on_board(*landing_spot):
            return False

        return True

    def _get_valid_actions(self):
        """Enumerate all currently legal action indices for the action mask.

        This method is called every step to build the boolean mask that
        MaskablePPO uses to zero out illegal action logits.  It iterates over
        all board cells and, depending on the current phase, checks:

          - setup:  which cells are valid placements for the next piece
          - move:   which (piece, destination) pairs are reachable slides
          - push:   which (square_piece, direction) pairs are valid pushes

        Returns:
            list[int]: Sorted list of valid action indices in [0, 1800).
        """
        valid_actions = []

        if self.current_phase == 'setup':
            # During setup, the only valid actions are piece placements.
            for y in range(10):
                for x in range(4):
                    if self._is_valid_placement(y, x):
                        valid_actions.append(1760 + y * 4 + x)
            return valid_actions

        if self.current_phase == 'move' and self.game.can_move():
            # Move phase: enumerate all reachable (source, dest) pairs for
            # the current player's pieces.
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
            # Push phase: enumerate all valid (square_piece, direction) pairs.
            # Only square pieces can push, and only in directions where the
            # push chain's landing spot is on the board.
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
        """Build a boolean mask over the full action space for MaskablePPO.

        Returns:
            np.ndarray: Boolean array of shape (1800,) where True indicates
                that the corresponding action index is legal in the current state.
        """
        valid_mask = np.zeros(1800, dtype=bool)
        for action in self._get_valid_actions():
            if 0 <= action < 1800:
                valid_mask[action] = True
        return valid_mask

    def action_masks(self):
        """Public API method required by MaskablePPO for action masking.

        sb3-contrib's MaskablePPO calls ``env.action_masks()`` (or looks for it
        via ``get_action_masks(env)``) at each step to obtain the boolean mask.
        This is the single integration point between the environment and the
        masking mechanism.

        Returns:
            np.ndarray: Boolean mask of shape (1800,).
        """
        return self._get_valid_actions_mask()

    # -------------------------------------------------------------------------
    # Gymnasium API
    # -------------------------------------------------------------------------

    def reset(self, seed=None, options=None):
        """Reset the environment to the standard starting position.

        Instead of requiring the agent to learn piece placement (which is a
        different strategic problem), we use the fixed initial layout from
        ``GameState.create_initial_game()``.  The agent starts directly in
        the move phase.  Piece placement during actual server games is handled
        separately by ``_auto_place()`` in the server code.

        Args:
            seed: Optional random seed for reproducibility.
            options: Unused; kept for Gymnasium API compatibility.

        Returns:
            tuple: (observation, info) where observation is a 205-element
                float32 array and info is a dict with diagnostic metadata.
        """
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
        """Execute one environment step: decode, validate, execute, and reward.

        The step logic proceeds as follows:
          1. Check for episode truncation (max_steps exceeded).
          2. Check for terminal state (no valid actions = current player loses).
          3. Decode the action integer into a phase-specific representation.
          4. Validate the decoded action; if invalid, substitute a random valid
             action and apply a small penalty (-0.05).  This should rarely
             happen when MaskablePPO is working correctly, but provides a
             safety net.
          5. Execute the action on the game state and compute reward.
          6. For push actions: check for game-over, apply edge proximity and
             round-threat shaping rewards, then switch turns.

        Args:
            action: Integer in [0, 1800) selected by the policy (or sampled
                from the masked action distribution).

        Returns:
            tuple: (observation, reward, terminated, truncated, info)
                - observation: 205-element float32 array
                - reward: float scalar
                - terminated: True if the game ended (win/loss)
                - truncated: True if max_steps was reached
                - info: dict with keys like 'action_type', 'current_player',
                  'phase', 'game_over', 'valid_actions'
        """
        reward = 0.0
        terminated = False
        truncated = False
        info = {}
        self.step_count += 1

        # --- Truncation guard: cap episodes to prevent infinite games ---
        if self.step_count >= self.max_steps:
            truncated = True
            observation = self._get_observation()
            info['action_type'] = 'truncated'
            return observation, 0.0, terminated, truncated, info

        valid_list = self._get_valid_actions()

        # --- No valid actions: the current player is stuck and loses ---
        if not valid_list:
            terminated = True
            self.game.game_over = True
            opponent = 'black' if self.game.current_player == 'white' else 'white'
            self.game.winner = opponent
            reward = -1.0  # Terminal loss
            observation = self._get_observation()
            info['action_type'] = 'no_valid_actions'
            return observation, reward, terminated, truncated, info

        # --- Decode the flat action integer into a phase-specific tuple ---
        phase, action_data = self._decode_action(action)

        # --- Validate the action; substitute a random valid one if invalid ---
        # MaskablePPO should prevent invalid actions, but this is a safety net
        # in case of edge cases or during evaluation with a non-masked policy.
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
            # Pick a uniformly random valid action as a fallback.
            action = int(self.np_random.choice(valid_list))
            phase, action_data = self._decode_action(action)
            reward -= 0.05  # Small penalty to discourage invalid action selection

        # ===================================================================
        # Execute the decoded action on the game state
        # ===================================================================

        if phase == 'place':
            # --- SETUP PHASE: place the next piece from the roster ---
            y, x = action_data
            team = self.game.current_player
            next_piece = self._get_next_piece(team)
            if next_piece:
                name, shape = next_piece
                success, _ = self.game.place_piece(y, x, team, shape, name)
                if success:
                    # Small placement reward with bonuses for central positions.
                    # Central columns (1, 2) and rows near the midline are
                    # strategically stronger in Push Fight.
                    reward += 0.001
                    if x in (1, 2):
                        reward += 0.002  # Central column bonus
                    if (team == 'white' and y in (3, 4)) or (team == 'black' and y in (5, 6)):
                        reward += 0.002  # Near-midline bonus

                    # Check if current team's setup is complete
                    status = self.game.get_placement_status(team)
                    if status['squares'] == 3 and status['rounds'] == 2:
                        opponent = 'black' if team == 'white' else 'white'
                        opp_status = self.game.get_placement_status(opponent)
                        if opp_status['squares'] == 3 and opp_status['rounds'] == 2:
                            # Both teams finished placing -- transition to move phase
                            self.game.start_game()
                            self.current_phase = 'move'
                        else:
                            # Switch to opponent's setup turn
                            self.game.current_player = opponent

            info['action_type'] = 'place'

        elif phase == 'move':
            # --- MOVE PHASE: slide a piece to a new cell ---
            piece_y, piece_x, dest_y, dest_x = action_data
            piece = self.game.board.get_piece(piece_y, piece_x)

            # Execute the move by directly updating the pieces grid.
            self.game.board.pieces[piece_y][piece_x] = None
            self.game.board.pieces[dest_y][dest_x] = piece
            self.game.moves_made += 1

            # After 2 moves (or if the player chooses to stop), transition
            # to the mandatory push phase.
            if not self.game.can_move():
                self.current_phase = 'push'

            # Positional reward: encourage good board positioning after each move.
            reward += self._edge_proximity_reward()

            info['action_type'] = 'move'

        elif phase == 'push':
            # --- PUSH PHASE: push a chain of pieces in a cardinal direction ---
            piece_y, piece_x, direction = action_data

            # Snapshot opponent's minimum kill-zone distance *before* the push
            # to measure whether this push created additional danger.
            opponent = 'black' if self.game.current_player == 'white' else 'white'
            opp_dist_before = self._min_kill_zone_distance(opponent)

            success = self.game.perform_push(piece_y, piece_x, direction)

            if not success:
                # This should not happen with proper action masking, but handle
                # it gracefully with a moderate penalty.
                reward = -0.5
                info['action_type'] = 'invalid_push'
                observation = self._get_observation()
                return observation, reward, terminated, truncated, info

            # Check if any piece was pushed off the board.
            self.game.check_game_over()

            if self.game.game_over:
                # Terminal state: +1 for winning, -1 for losing.
                terminated = True
                if self.game.winner == self.game.current_player:
                    reward = 1.0
                else:
                    reward = -1.0
            else:
                # --- Reward shaping for non-terminal pushes ---

                # Bonus if this push moved an opponent piece closer to the kill zone.
                opp_dist_after = self._min_kill_zone_distance(opponent)
                if opp_dist_after < opp_dist_before:
                    reward += 0.05  # Pushed opponent closer to danger

                # Bonus for each opponent round piece now sitting at edge_dist <= 1.
                # These pieces are one push away from the kill zone -- an
                # immediate threat that the agent should learn to create.
                for y in range(10):
                    for x in range(4):
                        piece = self.game.board.get_piece(y, x)
                        if (piece and piece != "OUT_OF_BOUNDS" and
                                piece.team == opponent and piece.shape == 'round' and
                                _edge_dist(y, x) <= 1):
                            reward += ROUND_THREAT_REWARD

                # Edge proximity reward computed *before* switching turns so the
                # reward reflects the pushing player's perspective.
                reward += self._edge_proximity_reward()

                # Turn is over: switch to the opponent and reset to move phase.
                self.game.switch_turn()
                self.current_phase = 'move'

                # After switching, check if the new player has any legal push.
                # If not, they lose immediately (you must push every turn).
                if not self.game.has_legal_push():
                    self.game.game_over = True
                    # The previous player (who just pushed) wins.
                    prev_player = 'black' if self.game.current_player == 'white' else 'white'
                    self.game.winner = prev_player
                    terminated = True
                    reward = -1.0  # Loss from the new current player's perspective

            info['action_type'] = 'push'

        # --- Build the final observation and info dict ---
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
        """Render the current board state to the console or as an RGB array.

        In "human" mode, prints a box-drawing-character framed board with piece
        labels (W/B for team, S/R for shape, * for anchor) and game status.

        Args:
            clear_screen: If True and render_mode is "human", clear the terminal
                before printing (uses ANSI escape codes).

        Returns:
            None for "human" mode; np.ndarray of shape (400, 300, 3) for
            "rgb_array" mode (placeholder -- not yet implemented with real
            graphics).
        """
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
                            row_str += "XXX "  # Kill zone cell
                        elif piece is None:
                            row_str += "... "  # Empty playable cell
                        elif piece == "OUT_OF_BOUNDS":
                            row_str += "### "  # Non-playable cell
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
        """Clean up resources (no-op for this environment)."""
        pass


class SelfPlayEnv(PushFightEnv):
    """Self-play wrapper: the agent controls one color; the opponent auto-plays.

    Self-play is the standard approach for training game-playing agents because:
      1. It avoids the need for hand-crafted opponent heuristics.
      2. The opponent improves alongside the agent, creating a natural curriculum.
      3. It prevents overfitting to a fixed opponent strategy.

    Each episode:
      - The agent is randomly assigned white or black (symmetric training).
      - An opponent model is sampled from a pool of previously saved snapshots.
      - If no snapshots exist (or with probability ``p_random``), the opponent
        plays uniformly random valid actions instead.
      - After the agent takes an action via ``step()``, the opponent auto-plays
        all of its turns until control returns to the agent.

    Snapshot pool mechanics:
      - ``SelfPlayCallback`` (in train.py) saves the current model to
        ``pool_dir`` every N training steps.
      - On each ``reset()``, ``_reload_opponent()`` samples a snapshot with
        linear weighting toward more recent ones (so the agent mostly faces
        near-current-strength opponents rather than its earliest weak versions).
      - The ``p_random`` parameter controls the probability that the opponent
        plays purely random instead of using a snapshot, ensuring diversity
        and preventing the agent from overfitting to a narrow set of strategies.

    Attributes:
        pool_dir: Directory containing opponent snapshot .zip files.
        p_random: Probability the opponent plays random actions this episode.
        opponent_model: The loaded MaskablePPO snapshot, or None for random play.
        agent_team: 'white' or 'black' -- which color the learning agent plays
            this episode (randomized each reset).
    """

    def __init__(self, pool_dir='models/pool', p_random=0.2, **kwargs):
        """Initialize the self-play environment.

        Args:
            pool_dir: Path to the directory containing opponent snapshot files
                (e.g., 'models/pool/snapshot_50000.zip').  Created automatically
                by SelfPlayCallback during training.
            p_random: Probability (0.0 to 1.0) that the opponent uses purely
                random valid actions instead of a snapshot model.  Higher values
                increase opponent diversity at the cost of weaker opposition.
                Typical values: 0.4 for easy, 0.1 for medium, 0.02 for hard.
            **kwargs: Passed through to PushFightEnv.__init__() (e.g.,
                flatten_obs, suppress_prints).
        """
        super().__init__(**kwargs)
        self.pool_dir = pool_dir
        self.p_random = p_random   # probability opponent plays purely random this episode
        self.opponent_model = None
        self.agent_team = 'white'  # updated each reset()

    # ------------------------------------------------------------------
    # Gymnasium API overrides
    # ------------------------------------------------------------------

    def reset(self, seed=None, options=None):
        """Reset the environment and randomly assign the agent's team color.

        After resetting the base environment, if the opponent moves first
        (i.e., the agent was assigned the non-starting color), we auto-play
        the opponent's turns until it is the agent's turn.

        Args:
            seed: Optional random seed.
            options: Unused; kept for Gymnasium API compatibility.

        Returns:
            tuple: (observation, info) from the agent's perspective.
        """
        # Randomly pick which color the learning agent plays this episode.
        # This ensures the policy learns symmetric play for both sides.
        self.agent_team = np.random.choice(['white', 'black'])
        self._reload_opponent()
        obs, info = super().reset(seed=seed, options=options)
        # If it's the opponent's turn first, auto-play until agent's turn.
        if self.game.current_player != self.agent_team:
            obs, info = self._drain_opponent_turns(obs, info)
        return obs, info

    def step(self, action):
        """Agent takes an action; then the opponent auto-plays until the agent's turn.

        This method:
          1. Executes the agent's action via the parent class's step().
          2. If the game is not over, loops to auto-play all opponent turns.
          3. If the game ends during the opponent's turns, translates the
             reward to the agent's perspective (+1 for agent win, -1 for loss).

        The agent only ever sees observations and rewards from its own turns,
        making the environment appear as a single-player MDP even though it
        models a two-player game.

        Args:
            action: Integer action selected by the agent's policy.

        Returns:
            tuple: (observation, reward, terminated, truncated, info) from
                the agent's perspective.
        """
        obs, reward, terminated, truncated, info = super().step(action)

        if terminated or truncated:
            return obs, reward, terminated, truncated, info

        # Auto-play all opponent turns until it is the agent's turn again.
        while not terminated and not truncated and self.game.current_player != self.agent_team:
            opp_action = self._get_opponent_action(obs)
            obs, _, terminated, truncated, info = super().step(opp_action)

        # If the game ended during the opponent's turn, map the outcome
        # to the agent's reward: +1 if the agent won, -1 if the agent lost.
        if terminated and self.game.game_over:
            reward = 1.0 if self.game.winner == self.agent_team else -1.0

        return obs, reward, terminated, truncated, info

    # ------------------------------------------------------------------
    # Opponent helpers
    # ------------------------------------------------------------------

    def _get_opponent_action(self, obs):
        """Select an action for the opponent (snapshot model or random).

        The opponent decision process:
          1. If no model is loaded, or if a random roll (based on p_random)
             succeeds, play a uniformly random valid action.
          2. Otherwise, use the snapshot model's ``predict()`` with the current
             observation and action mask.
          3. If the model prediction raises any exception (e.g., shape
             mismatch from an older snapshot), fall back to random.

        Args:
            obs: The current observation array (205 floats).

        Returns:
            int: An action index in [0, 1800).
        """
        valid = self._get_valid_actions()
        if not valid:
            return 0  # No valid actions; step() will handle the terminal state

        # Decide whether to use the snapshot model or play randomly.
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

        # Uniform random over valid actions.
        return int(np.random.choice(valid))

    def _reload_opponent(self):
        """Load a snapshot model from the pool directory for this episode's opponent.

        Snapshot selection uses linear weighting toward more recent snapshots:
        if there are N snapshots sorted by training step, the i-th snapshot
        (0-indexed) gets weight (i + 1).  This means the most recent snapshot
        is N times more likely to be chosen than the oldest.

        Rationale: uniform sampling would mean the agent spends most episodes
        against its earliest (weakest) versions, slowing down learning.  Linear
        weighting creates a curriculum that tracks the agent's improving skill.

        If the pool directory does not exist, is empty, or a random roll
        (based on p_random) succeeds, the opponent is set to None (random play).
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
        # Linear weights: oldest snapshot gets weight 1, most recent gets weight n.
        # This biases selection toward newer (stronger) opponents.
        weights = np.arange(1, n + 1, dtype=float)
        weights /= weights.sum()
        snapshot = np.random.choice(snapshots_sorted, p=weights)

        path = os.path.join(self.pool_dir, snapshot)
        try:
            from sb3_contrib import MaskablePPO
            # Load the snapshot without binding it to an env -- it is only
            # used for predict() calls, not for training.
            self.opponent_model = MaskablePPO.load(path, device='cpu')
        except Exception:
            self.opponent_model = None

    def _drain_opponent_turns(self, obs, info):
        """Auto-play opponent turns at the start of an episode.

        Called from ``reset()`` when the opponent has the first move.  Loops
        until control passes to the agent or the game ends.

        Args:
            obs: Current observation array.
            info: Current info dict from the most recent reset/step.

        Returns:
            tuple: Updated (obs, info) after all opponent turns are complete.
        """
        while self.game.current_player != self.agent_team and not self.game.game_over:
            action = self._get_opponent_action(obs)
            obs, _, terminated, truncated, info = super().step(action)
            if terminated or truncated:
                break
        return obs, info
