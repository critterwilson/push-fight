"""Random agent implementation for testing."""

import random
from app.rl.base_agent import BaseAgent
from app.engine.game_state import GameState


class RandomAgent(BaseAgent):
    """
    Random agent that selects random valid actions.
    
    Useful for testing and as a baseline for RL training.
    """
    
    def __init__(self, seed=None):
        """
        Initialize random agent.
        
        Args:
            seed: Random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)
    
    def get_action(self, game_state: GameState):
        """
        Get a random valid action.
        
        Args:
            game_state: Current GameState object
            
        Returns:
            dict: Action dictionary
        """
        # Check if we're in move phase
        if game_state.can_move():
            valid_moves = self.get_valid_moves(game_state)
            if valid_moves:
                move = random.choice(valid_moves)
                return {
                    'type': 'move',
                    'from': move['from'],
                    'to': move['to']
                }
        
        # Must be in push phase
        valid_pushes = self.get_valid_pushes(game_state)
        if valid_pushes:
            push = random.choice(valid_pushes)
            return {
                'type': 'push',
                'piece': push['piece'],
                'direction': push['direction']
            }
        
        # No valid actions (shouldn't happen in normal play)
        return None
    
    def reset(self):
        """Reset agent state (no-op for random agent)."""
        pass
