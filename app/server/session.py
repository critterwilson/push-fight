"""
Session management for the Push Fight web server.

Each game session holds a GameState, game mode, an optional AI agent,
and the set of active WebSocket connections for that session.
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
    session_id: str
    game: GameState
    mode: str               # 'pvp' or 'pvai'
    ai_team: str            # 'black' — AI always plays black in pvai mode
    agent: Optional["PushFightAgent"] = None
    websockets: List[WebSocket] = field(default_factory=list)


class SessionManager:
    """In-memory store of active game sessions."""

    # Difficulty → model file mapping
    _MODEL_PATHS = {
        "easy":   "models/easy.zip",
        "medium": "models/medium.zip",
    }
    _DEFAULT_MODEL = "models/push_fight_ppo.zip"

    def __init__(self):
        self._sessions: Dict[str, GameSession] = {}

    def create(self, mode: str = "pvp", difficulty: str = "medium") -> GameSession:
        """Create a new game session and return it."""
        session_id = str(uuid.uuid4())
        game = GameState.create_initial_game()

        agent = None
        if mode == "pvai":
            agent = self._load_agent(difficulty)

        session = GameSession(
            session_id=session_id,
            game=game,
            mode=mode,
            ai_team="black",
            agent=agent,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[GameSession]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _load_agent(self, difficulty: str) -> "PushFightAgent":
        from app.rl.agent import PushFightAgent

        model_path = self._MODEL_PATHS.get(difficulty, self._DEFAULT_MODEL)
        if not os.path.exists(model_path):
            model_path = self._DEFAULT_MODEL
        return PushFightAgent(model_path)
