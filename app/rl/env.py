"""Gymnasium environment for Push Fight game."""

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from app.engine.game_state import GameState


class PushFightEnv(gym.Env):
    """
    Gymnasium environment for Push Fight game.
    
    Observation space: 10x4x5 array representing board state
    - Features per cell: [has_piece, is_white, is_square, is_anchor, is_kill_zone]
    
    Action space: MultiDiscrete for move and push phases
    - Move phase: [piece_y, piece_x, dest_y, dest_x]
    - Push phase: [piece_y, piece_x, direction]
    """
    
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}
    
    def __init__(self, render_mode=None):
        super().__init__()
        
        self.render_mode = render_mode
        self.game = None
        
        # Observation space: 10x4x5 (height x width x features)
        # Features: [has_piece, is_white, is_square, is_anchor, is_kill_zone]
        self.observation_space = spaces.Box(
            low=0, high=1, shape=(10, 4, 5), dtype=np.float32
        )
        
        # Action space: MultiDiscrete
        # For move: [piece_y (0-9), piece_x (0-3), dest_y (0-9), dest_x (0-3)]
        # For push: [piece_y (0-9), piece_x (0-3), direction (0-3: up, down, left, right)]
        # We'll use a flat action space and decode it
        # Max actions: 10*4*10*4 = 1600 for moves, 10*4*4 = 160 for pushes
        # Total: 1760 possible actions
        self.action_space = spaces.Discrete(1760)  # Will be decoded
        
        # Track current phase (move or push)
        self.current_phase = 'move'  # 'move' or 'push'
        self.moves_made = 0
        
    def _get_observation(self):
        """
        Convert game state to observation array.
        
        Returns:
            np.array: 10x4x5 array with features per cell
        """
        obs = np.zeros((10, 4, 5), dtype=np.float32)
        
        for y in range(10):
            for x in range(4):
                # Feature 4: is_kill_zone
                if self.game.board.grid[y][x] == -1:
                    obs[y, x, 4] = 1.0
                
                # Get piece at this position
                piece = self.game.board.get_piece(y, x)
                if piece and piece != "OUT_OF_BOUNDS":
                    # Feature 0: has_piece
                    obs[y, x, 0] = 1.0
                    
                    # Feature 1: is_white (1.0) or is_brown (0.0)
                    obs[y, x, 1] = 1.0 if piece.team == 'white' else 0.0
                    
                    # Feature 2: is_square (1.0) or is_round (0.0)
                    obs[y, x, 2] = 1.0 if piece.shape == 'square' else 0.0
                    
                    # Feature 3: is_anchor
                    if self.game.board.anchor_pos[0] is not None:
                        if (y, x) == self.game.board.anchor_pos:
                            obs[y, x, 3] = 1.0
        
        return obs
    
    def _decode_action(self, action):
        """
        Decode flat action integer into move or push action.
        
        Args:
            action: Integer action (0-1759)
            
        Returns:
            tuple: (phase, action_data)
            - For move: ('move', (piece_y, piece_x, dest_y, dest_x))
            - For push: ('push', (piece_y, piece_x, direction))
        """
        if self.current_phase == 'move' and self.game.can_move():
            # Move phase: 10*4*10*4 = 1600 possible actions
            if action < 1600:
                piece_y = action // (4 * 10 * 4)
                remainder = action % (4 * 10 * 4)
                piece_x = remainder // (10 * 4)
                remainder = remainder % (10 * 4)
                dest_y = remainder // 4
                dest_x = remainder % 4
                return ('move', (piece_y, piece_x, dest_y, dest_x))
            else:
                # Invalid move action
                return (None, None)
        else:
            # Push phase: 10*4*4 = 160 possible actions
            push_action = action - 1600
            if 0 <= push_action < 160:
                piece_y = push_action // (4 * 4)
                remainder = push_action % (4 * 4)
                piece_x = remainder // 4
                direction_idx = remainder % 4
                # Directions: 0=up, 1=down, 2=left, 3=right
                directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                direction = directions[direction_idx]
                return ('push', (piece_y, piece_x, direction))
            else:
                # Invalid push action
                return (None, None)
    
    def _get_valid_actions(self):
        """
        Get list of valid action indices for current state.
        
        Returns:
            list: List of valid action integers
        """
        valid_actions = []
        
        if self.current_phase == 'move' and self.game.can_move():
            # Get all valid moves
            for y in range(10):
                for x in range(4):
                    piece = self.game.board.get_piece(y, x)
                    if (piece and piece != "OUT_OF_BOUNDS" and 
                        piece.team == self.game.current_player):
                        valid_moves = self.game.board.get_valid_moves(y, x)
                        for dest_y, dest_x in valid_moves:
                            # Encode move action
                            action = y * (4 * 10 * 4) + x * (10 * 4) + dest_y * 4 + dest_x
                            valid_actions.append(action)
        else:
            # Push phase: get all valid pushes
            for y in range(10):
                for x in range(4):
                    piece = self.game.board.get_piece(y, x)
                    if (piece and piece != "OUT_OF_BOUNDS" and 
                        piece.team == self.game.current_player and
                        piece.shape == 'square'):
                        # Try all directions
                        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                        for dir_idx, direction in enumerate(directions):
                            # Check if push is valid (simplified check)
                            chain, landing_spot = self.game.board.get_push_chain(y, x, *direction)
                            # Check anchor
                            anchor_blocks = False
                            if self.game.board.anchor_pos[0] is not None:
                                for pos in chain:
                                    if pos == self.game.board.anchor_pos:
                                        anchor_blocks = True
                                        break
                            # Check side rail
                            side_rail_blocks = not self.game.board.is_on_board(*landing_spot)
                            
                            if not anchor_blocks and not side_rail_blocks:
                                # Encode push action
                                action = 1600 + y * (4 * 4) + x * 4 + dir_idx
                                valid_actions.append(action)
        
        return valid_actions if valid_actions else [0]  # At least one action (even if invalid)
    
    def reset(self, seed=None, options=None):
        """Reset the environment to initial state."""
        super().reset(seed=seed)
        
        self.game = GameState.create_initial_game()
        self.current_phase = 'move'
        self.moves_made = 0
        
        observation = self._get_observation()
        info = {
            'current_player': self.game.current_player,
            'phase': self.current_phase,
            'moves_made': self.moves_made
        }
        
        return observation, info
    
    def step(self, action):
        """
        Execute one step in the environment.
        
        Args:
            action: Action to take (integer)
            
        Returns:
            observation, reward, terminated, truncated, info
        """
        reward = 0.0
        terminated = False
        truncated = False
        info = {}
        
        # Decode action
        phase, action_data = self._decode_action(action)
        
        if phase is None:
            # Invalid action
            reward = -0.1  # Small penalty for invalid action
            info['invalid_action'] = True
            observation = self._get_observation()
            return observation, reward, terminated, truncated, info
        
        if phase == 'move':
            piece_y, piece_x, dest_y, dest_x = action_data
            
            # Validate move
            piece = self.game.board.get_piece(piece_y, piece_x)
            if (not piece or piece == "OUT_OF_BOUNDS" or 
                piece.team != self.game.current_player):
                reward = -0.1
                info['invalid_action'] = True
                observation = self._get_observation()
                return observation, reward, terminated, truncated, info
            
            valid_moves = self.game.board.get_valid_moves(piece_y, piece_x)
            if (dest_y, dest_x) not in valid_moves:
                reward = -0.1
                info['invalid_action'] = True
                observation = self._get_observation()
                return observation, reward, terminated, truncated, info
            
            # Execute move
            self.game.board.pieces[piece_y][piece_x] = None
            self.game.board.pieces[dest_y][dest_x] = piece
            self.game.moves_made += 1
            self.moves_made += 1
            
            # Check if we should switch to push phase
            if not self.game.can_move():
                self.current_phase = 'push'
            
            reward = 0.0  # Small reward for valid move
            info['action_type'] = 'move'
            info['moves_made'] = self.game.moves_made
            
        elif phase == 'push':
            piece_y, piece_x, direction = action_data
            
            # Execute push
            success = self.game.perform_push(piece_y, piece_x, direction)
            
            if not success:
                reward = -0.1
                info['invalid_action'] = True
                observation = self._get_observation()
                return observation, reward, terminated, truncated, info
            
            # Check for game over (handled by perform_push for kill zone, but also check square count)
            self.game.check_game_over()
            
            if self.game.game_over:
                terminated = True
                if self.game.winner == self.game.current_player:
                    reward = 1.0  # Win
                else:
                    reward = -1.0  # Loss (shouldn't happen in single-agent, but for completeness)
            else:
                # Switch turns
                self.game.switch_turn()
                self.current_phase = 'move'
                self.moves_made = 0
                reward = 0.0  # Small reward for valid push
            
            info['action_type'] = 'push'
            info['push_completed'] = True
            
            # Check if opponent is trapped
            if not self.game.game_over and not self.game.has_legal_push():
                # Opponent has no legal pushes - we win
                self.game.game_over = True
                self.game.winner = self.game.current_player
                terminated = True
                reward = 1.0
        
        # Check for terminal state based on square piece count (state evaluator)
        if not terminated:
            self.game.check_game_over()
            if self.game.game_over:
                terminated = True
                if self.game.winner == self.game.current_player:
                    reward = 1.0
                else:
                    reward = -1.0
        
        observation = self._get_observation()
        info['current_player'] = self.game.current_player
        info['phase'] = self.current_phase
        info['game_over'] = self.game.game_over
        
        return observation, reward, terminated, truncated, info
    
    def render(self):
        """Render the environment (placeholder for now)."""
        if self.render_mode == "human":
            # Could print board or use PyGame
            pass
        elif self.render_mode == "rgb_array":
            # Return RGB array for rendering
            return np.zeros((400, 300, 3), dtype=np.uint8)
    
    def close(self):
        """Clean up resources."""
        pass
