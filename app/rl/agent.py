import os
import numpy as np
from sb3_contrib import MaskablePPO
from app.rl.env import PushFightEnv

class PushFightAgent:
    """Unified AI Agent for Push Fight."""
    
    def __init__(self, model_path):
        """
        Initialize the agent and load the model.
        
        Args:
            model_path: Path to the .zip model file or directory containing it.
        """
        self.env = PushFightEnv(flatten_obs=True, suppress_prints=True)
        self.model = self._load_model(model_path)

    def _load_model(self, model_path):
        """Load the model with path resolution logic."""
        original_path = model_path
        
        # Handle directory input (look for zip with same name)
        if os.path.isdir(model_path):
            dir_name = os.path.basename(model_path.rstrip('/'))
            parent_dir = os.path.dirname(model_path) if os.path.dirname(model_path) else '.'
            
            # Try parent_dir/name.zip (standard SB3 save format)
            zip_path = os.path.join(parent_dir, dir_name + ".zip")
            if os.path.exists(zip_path):
                model_path = zip_path
            else:
                # Try current directory with name.zip
                zip_path = dir_name + ".zip"
                if os.path.exists(zip_path):
                    model_path = zip_path
        
        # Ensure extension
        if not model_path.endswith('.zip'):
            zip_path = model_path + ".zip"
            if os.path.exists(zip_path):
                model_path = zip_path
                
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {original_path}")
            
        return MaskablePPO.load(model_path, env=self.env)

    def get_action(self, game_state):
        """
        Get the next action from the AI for the given game state.
        
        Returns:
            dict: Action dictionary {'type': 'move'|'push', ...} or None
        """
        # Sync environment
        self.env.game = game_state
        self.env.current_phase = 'move' if game_state.can_move() else 'push'
        self.env.moves_made = game_state.moves_made
        
        # Get observation and masks
        obs = self.env._get_observation()
        action_masks = self.env.action_masks()
        
        # Predict
        action, _states = self.model.predict(obs, deterministic=True, action_masks=action_masks)
        
        # Decode
        phase, action_data = self.env._decode_action(int(action))
        
        # Fallback if decode fails (shouldn't happen with valid masks, but for safety)
        if phase is None:
            valid_actions = np.where(action_masks)[0]
            if len(valid_actions) > 0:
                action = int(np.random.choice(valid_actions))
                phase, action_data = self.env._decode_action(action)
        
        if phase == 'move':
            piece_y, piece_x, dest_y, dest_x = action_data
            return {'type': 'move', 'from': (piece_y, piece_x), 'to': (dest_y, dest_x)}
            
        elif phase == 'push':
            piece_y, piece_x, direction = action_data
            return {'type': 'push', 'piece': (piece_y, piece_x), 'direction': direction}
            
        return None