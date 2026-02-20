"""
Session management for the Push Fight web server.

Each game session bundles together:
  - A GameState (board, turn tracking, win conditions)
  - Game mode ('pvp' or 'pvai')
  - An optional AI agent (loaded from a trained RL model)
  - Active WebSocket connections for real-time state broadcasting

Sessions are stored in-memory — restarting the server clears all active
games.  Persistent storage is handled separately by the save/load system.

The SessionManager acts as a lightweight dependency-injection container:
it creates sessions, loads AI models by difficulty tier, and provides
lookup/deletion for the handler layer.
"""

import uuid
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, List, TYPE_CHECKING

from fastapi import WebSocket

from app.engine.game_state import GameState

if TYPE_CHECKING:
    from app.rl.agent import PushFightAgent


@dataclass
class GameSession:
    """A single active game with its associated connections and AI.

    Attributes:
        session_id: UUID string uniquely identifying this game.
        game:       The engine GameState tracking board and rules.
        mode:       'pvp' (two humans) or 'pvai' (human vs RL agent).
        ai_team:    Which team the AI controls ('white' or 'black').
        agent:      The loaded RL agent, or None for PvP / missing model.
        websockets: Active WebSocket connections subscribed to this game.
    """
    session_id: str
    game: GameState
    mode: str
    ai_team: str
    agent: Optional["PushFightAgent"] = None
    websockets: List[WebSocket] = field(default_factory=list)


class SessionManager:
    """In-memory store of active game sessions with AI model loading.

    Difficulty levels map to pre-trained model files:
      - easy:   models/easy.zip    (fewer training steps)
      - medium: models/medium.zip  (moderate training)
      - hard:   models/push_fight_ppo.zip (full training run)
    """

    # Map difficulty labels to model file paths
    _MODEL_PATHS = {
        "easy":   "models/easy.zip",
        "medium": "models/medium.zip",
    }
    _DEFAULT_MODEL = "models/push_fight_ppo.zip"

    def __init__(self):
        self._sessions: Dict[str, GameSession] = {}

    def create(self, mode: str = "pvp", difficulty: str = "medium",
               ai_team: str = "black") -> GameSession:
        """Create a new game session with optional AI opponent.

        In PvAI mode, the AI agent is loaded from the difficulty-appropriate
        model file.  If the AI plays white, the human (black) places first,
        so current_player is set to 'black' for the setup phase.

        Args:
            mode:       'pvp' or 'pvai'.
            difficulty: AI strength tier ('easy', 'medium', 'hard').
            ai_team:    Which team the AI controls.

        Returns:
            The newly created GameSession.
        """
        session_id = str(uuid.uuid4())
        game = GameState.create_custom_game()

        agent = None
        if mode == "pvai":
            agent = self._load_agent(difficulty)
            # When AI is white, human sets up black pieces first
            if ai_team == "white":
                game.current_player = "black"

        session = GameSession(
            session_id=session_id,
            game=game,
            mode=mode,
            ai_team=ai_team,
            agent=agent,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[GameSession]:
        """Look up a session by ID, returning None if not found."""
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        """Remove a session from the store (e.g. when all clients disconnect)."""
        self._sessions.pop(session_id, None)

    def _load_agent(self, difficulty: str) -> Optional["PushFightAgent"]:
        """Load a pre-trained RL agent for the given difficulty tier.

        Falls back to the default model if the difficulty-specific file
        is missing. Returns None if no model file exists at all (the AI
        will fall back to random moves).
        """
        from app.rl.agent import PushFightAgent

        model_path = self._MODEL_PATHS.get(difficulty, self._DEFAULT_MODEL)
        if not os.path.exists(model_path):
            model_path = self._DEFAULT_MODEL
        try:
            return PushFightAgent(model_path)
        except FileNotFoundError:
            return None
