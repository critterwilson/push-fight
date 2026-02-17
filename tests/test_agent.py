import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from app.rl.agent import PushFightAgent
from app.engine.game_state import GameState

class TestPushFightAgent(unittest.TestCase):
    @patch('app.rl.agent.MaskablePPO')
    @patch('os.path.exists')
    def test_initialization(self, mock_exists, mock_ppo):
        """Test that the agent initializes and loads the model."""
        mock_exists.return_value = True
        agent = PushFightAgent('models/test_model.zip')
        mock_ppo.load.assert_called_once()
        self.assertIsNotNone(agent.model)
        self.assertIsNotNone(agent.env)

    @patch('app.rl.agent.MaskablePPO')
    @patch('os.path.exists')
    def test_get_action_move(self, mock_exists, mock_ppo):
        """Test that get_action returns a correctly formatted move action."""
        mock_exists.return_value = True
        
        # Setup mock model
        mock_model = MagicMock()
        mock_ppo.load.return_value = mock_model
        # Mock predict to return a specific action index
        mock_model.predict.return_value = (0, None)
        
        agent = PushFightAgent('models/test_model.zip')
        
        # Mock environment decoding
        agent.env._decode_action = MagicMock(return_value=('move', (4, 0, 3, 0)))
        agent.env.action_masks = MagicMock(return_value=np.ones(1760, dtype=bool))
        agent.env._get_observation = MagicMock(return_value=np.zeros(203))
        
        game = GameState.create_initial_game()
        action = agent.get_action(game)
        
        self.assertEqual(action['type'], 'move')
        self.assertEqual(action['from'], (4, 0))
        self.assertEqual(action['to'], (3, 0))

    @patch('app.rl.agent.MaskablePPO')
    @patch('os.path.exists')
    def test_get_action_push(self, mock_exists, mock_ppo):
        """Test that get_action returns a correctly formatted push action."""
        mock_exists.return_value = True
        mock_model = MagicMock()
        mock_ppo.load.return_value = mock_model
        mock_model.predict.return_value = (1600, None) # Push action range
        
        agent = PushFightAgent('models/test_model.zip')
        
        agent.env._decode_action = MagicMock(return_value=('push', (4, 0, (1, 0))))
        agent.env.action_masks = MagicMock(return_value=np.ones(1760, dtype=bool))
        agent.env._get_observation = MagicMock(return_value=np.zeros(203))
        
        game = GameState.create_initial_game()
        action = agent.get_action(game)
        
        self.assertEqual(action['type'], 'push')
        self.assertEqual(action['piece'], (4, 0))
        self.assertEqual(action['direction'], (1, 0))

if __name__ == '__main__':
    unittest.main()