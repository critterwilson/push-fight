"""Simple agent interface for Push Fight game (no Gym dependency)."""

from abc import ABC, abstractmethod
from app.engine.game_state import GameState


class SimpleAgent(ABC):
    """
    Simple agent interface that works directly with GameState.
    
    This interface is simpler than Gym and doesn't require Gymnasium to be installed.
    Useful for custom agents that want to work directly with the game logic.
    """
    
    @abstractmethod
    def get_action(self, game_state: GameState):
        """
        Get the next action for the given game state.
        
        Args:
            game_state: Current GameState object
            
        Returns:
            dict: Action dictionary with keys:
                - 'type': 'move' or 'push'
                - 'from': (y, x) tuple for piece position (for move)
                - 'to': (y, x) tuple for destination (for move)
                - 'piece': (y, x) tuple for pushing piece (for push)
                - 'direction': (dy, dx) tuple for push direction (for push)
        """
        pass
    
    @abstractmethod
    def get_observation(self, game_state: GameState):
        """
        Get observation representation of the game state.
        
        Args:
            game_state: Current GameState object
            
        Returns:
            Any: Observation representation (format depends on agent)
        """
        pass
    
    def reset(self):
        """Reset agent state (optional, for agents with internal state)."""
        pass
