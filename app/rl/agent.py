"""Inference wrapper for a trained Push Fight RL agent.

This module provides ``PushFightAgent``, which loads a trained MaskablePPO
model and translates game states into action dictionaries that the web server
(``AIService``) or CLI tools can execute.

Architecture overview
---------------------
The agent does NOT interact with the Gymnasium environment's ``step()``
method.  Instead, it:
  1. Receives an external ``GameState`` object (from the game engine).
  2. Syncs a lightweight ``PushFightEnv`` instance to that state (by pointing
     ``env.game`` at the external GameState and updating ``env.current_phase``).
  3. Generates an observation via ``env._get_observation()`` and an action mask
     via ``env.action_masks()``.
  4. Calls ``model.predict()`` to get the best action under the mask.
  5. Decodes the flat action integer back into a human-readable dict
     (e.g., ``{'type': 'move', 'from': (2,1), 'to': (4,1)}``).

This design decouples the RL model from the game loop: the server manages the
authoritative GameState, and the agent is a stateless "advisor" that just
recommends the next action.

Why MaskablePPO?
----------------
MaskablePPO (from sb3-contrib) is used because Push Fight's 1800-action
discrete space contains many illegal actions in any given state.  The action
mask zeroes out illegal logits before the softmax, ensuring the policy only
ever considers legal moves.  At inference time this means ``predict()`` will
always return a legal action (assuming the mask is correct), but we include
a random-fallback safety net just in case.

Model path resolution
---------------------
Stable-Baselines3 saves models as .zip files.  Users may pass a directory
path, a path without the .zip extension, or the full .zip path.  The
``_load_model`` method handles all three conventions.
"""

import os
import numpy as np
from sb3_contrib import MaskablePPO
from app.rl.env import PushFightEnv

class PushFightAgent:
    """Wraps a trained MaskablePPO model for Push Fight action prediction.

    This class is the primary interface between the RL system and the rest of
    the application (web server, CLI).  It handles:
      - Model loading with flexible path resolution
      - Game state synchronization (external GameState -> env observation)
      - Action prediction with action masking
      - Fallback to random valid actions if prediction fails

    Usage:
        agent = PushFightAgent("models/easy")
        action = agent.get_action(game_state)
        # action = {'type': 'move', 'from': (2,1), 'to': (4,1)}
        # or       {'type': 'push', 'piece': (3,2), 'direction': (-1,0)}
        # or       None (during setup phase)

    Attributes:
        env: A lightweight PushFightEnv instance used only for observation /
            mask generation -- its step() method is never called.
        model: The loaded MaskablePPO model used for action prediction.
    """

    def __init__(self, model_path):
        """Initialize the agent by loading a trained model.

        Args:
            model_path: Path to the trained MaskablePPO model.  Can be:
                - A .zip file path (e.g., "models/easy.zip")
                - A path without extension (e.g., "models/easy" -- .zip is appended)
                - A directory path (e.g., "models/easy/" -- looks for sibling .zip)

        Raises:
            FileNotFoundError: If the model file cannot be located.
        """
        # Create a lightweight env instance for observation/mask generation.
        # This env is never stepped -- it is only used to convert a GameState
        # into the 205-element observation vector and action mask that the
        # MaskablePPO model expects.
        self.env = PushFightEnv(flatten_obs=True, suppress_prints=True)
        self.model = self._load_model(model_path)

    def _load_model(self, model_path):
        """Load a MaskablePPO model with flexible path resolution.

        Stable-Baselines3 saves models as .zip files, but users often pass
        the path without the extension or as a directory.  This method tries
        several conventions to find the actual file:

          1. If model_path is a directory, look for a sibling .zip file with
             the same name (e.g., "models/easy/" -> "models/easy.zip").
          2. If model_path lacks a .zip extension, try appending it.
          3. If the file still isn't found, raise FileNotFoundError.

        Args:
            model_path: User-supplied path (file, directory, or extensionless).

        Returns:
            MaskablePPO: The loaded model, bound to self.env.

        Raises:
            FileNotFoundError: If no model file can be located.
        """
        original_path = model_path

        # Handle directory input: look for a .zip file with the same base name
        # in the parent directory (e.g., models/easy/ -> models/easy.zip).
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

        # If path doesn't end with .zip, try appending the extension.
        if not model_path.endswith('.zip'):
            zip_path = model_path + ".zip"
            if os.path.exists(zip_path):
                model_path = zip_path

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {original_path}")

        # Load the model and bind it to our env so predict() can access
        # the observation and action spaces.
        return MaskablePPO.load(model_path, env=self.env)

    def get_action(self, game_state):
        """Get the AI's recommended action for the given game state.

        This is the main public method called by the web server's AIService
        and the CLI play-against-ai script.  It synchronizes the internal
        env to the provided game state, generates an observation and action
        mask, runs the model's predict() method, and decodes the result into
        a structured action dictionary.

        During the setup phase (piece placement), this method returns None
        because placement is handled separately by the server's _auto_place()
        logic -- the RL agent is only trained on the move/push phases.

        Args:
            game_state: A ``GameState`` instance representing the current
                board position, current player, moves made, etc.

        Returns:
            dict or None:
                - ``{'type': 'move', 'from': (y, x), 'to': (y, x)}`` for a
                  piece slide during the move phase.
                - ``{'type': 'push', 'piece': (y, x), 'direction': (dy, dx)}``
                  for a push during the push phase.
                - ``None`` during the setup phase (placement handled elsewhere).
        """
        # Setup phase is handled by the server via _auto_place; RL not used here.
        if game_state.setup_mode:
            return None

        # Sync the lightweight env to the external game state.
        # We point env.game directly at the caller's GameState so that
        # _get_observation() and action_masks() reflect the real board.
        self.env.game = game_state
        # Determine the current phase from the game state: if the player
        # can still make optional moves, we are in 'move' phase; otherwise
        # it is the mandatory 'push' phase.
        self.env.current_phase = 'move' if game_state.can_move() else 'push'
        self.env.moves_made = game_state.moves_made

        # Generate the 205-element observation and 1800-element boolean mask.
        obs = self.env._get_observation()
        action_masks = self.env.action_masks()

        # Ask the MaskablePPO model for the best action.
        # deterministic=True means we take the argmax of the masked policy
        # rather than sampling -- this gives the strongest play at inference.
        action, _states = self.model.predict(obs, deterministic=True, action_masks=action_masks)

        # Decode the flat action integer into a phase-specific representation.
        phase, action_data = self.env._decode_action(int(action))

        # Fallback: if decoding fails (shouldn't happen with a correct mask,
        # but provides a safety net), pick a random valid action instead.
        if phase is None:
            valid_actions = np.where(action_masks)[0]
            if len(valid_actions) > 0:
                action = int(np.random.choice(valid_actions))
                phase, action_data = self.env._decode_action(action)

        # Convert the decoded action into the dict format expected by callers.
        if phase == 'move':
            piece_y, piece_x, dest_y, dest_x = action_data
            return {'type': 'move', 'from': (piece_y, piece_x), 'to': (dest_y, dest_x)}

        elif phase == 'push':
            piece_y, piece_x, direction = action_data
            return {'type': 'push', 'piece': (piece_y, piece_x), 'direction': direction}

        return None
