"""
Tests for the PushFightAgent wrapper (app.rl.agent).

The PushFightAgent class loads a trained MaskablePPO model from disk and
exposes a get_action(game_state) method that the server calls during PvAI
games. It bridges the gap between the RL environment's integer action space
and the server's structured action dictionaries (with 'type', 'from'/'to'
or 'piece'/'direction' keys).

Testing strategy:
  - The MaskablePPO model and os.path.exists are fully mocked — these tests
    do NOT load a real trained model or touch the filesystem.
  - The environment's internal methods (_decode_action, action_masks,
    _get_observation) are also mocked to control the exact action the
    "model" returns, ensuring deterministic assertions.
  - Two key scenarios are tested: get_action producing a move action and
    get_action producing a push action, verifying the dict structure.
"""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from app.rl.agent import PushFightAgent
from app.engine.game_state import GameState


class TestPushFightAgent(unittest.TestCase):
    """Tests for PushFightAgent initialization and action formatting.

    Each test mocks MaskablePPO.load and os.path.exists so that no real
    model file is required. The agent's internal env methods are also
    mocked to produce predictable action decodings.
    """

    @patch('app.rl.agent.MaskablePPO')
    @patch('os.path.exists')
    def test_initialization(self, mock_exists, mock_ppo):
        """Verify that the agent constructor loads the model file via
        MaskablePPO.load and that both model and env attributes are set.
        mock_exists returns True so the file-existence check passes."""
        mock_exists.return_value = True
        agent = PushFightAgent('models/test_model.zip')
        mock_ppo.load.assert_called_once()
        self.assertIsNotNone(agent.model)
        self.assertIsNotNone(agent.env)

    @patch('app.rl.agent.MaskablePPO')
    @patch('os.path.exists')
    def test_get_action_move(self, mock_exists, mock_ppo):
        """When the model predicts a move-range action (decoded as a 'move'),
        get_action must return a dict with type='move', from=(y,x), to=(y,x).

        Mocks:
          - mock_model.predict returns action index 0.
          - env._decode_action maps 0 to ('move', (4, 0, 3, 0)).
          - env.action_masks returns all-True (all actions valid).
          - env._get_observation returns a zero vector (dummy observation).
        """
        mock_exists.return_value = True

        # Setup mock model to return a specific action index
        mock_model = MagicMock()
        mock_ppo.load.return_value = mock_model
        mock_model.predict.return_value = (0, None)

        agent = PushFightAgent('models/test_model.zip')

        # Mock environment decoding to produce a move action
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
        """When the model predicts a push-range action (decoded as a 'push'),
        get_action must return a dict with type='push', piece=(y,x),
        direction=(dy,dx).

        Mocks:
          - mock_model.predict returns action index 1600 (push range).
          - env._decode_action maps 1600 to ('push', (4, 0, (1, 0))).
        """
        mock_exists.return_value = True
        mock_model = MagicMock()
        mock_ppo.load.return_value = mock_model
        mock_model.predict.return_value = (1600, None)  # Push action range

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