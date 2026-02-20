"""
AI turn execution — runs the RL agent (or random fallback) step-by-step.

This service drives the AI player's turn in PvAI mode.  It uses the
trained MaskablePPO agent (if a model file exists) or falls back to
random valid actions.

The AI turn is executed asynchronously with deliberate delays between
actions so the human player can observe the AI's decision-making:

  1. Short pause before the first action (0.4s).
  2. For each action (up to 2 moves + 1 push):
     a. Broadcast an 'ai_action' preview event (shows the intended action).
     b. Wait 0.5s for the frontend to animate the preview.
     c. Execute the action on the engine.
     d. Broadcast the updated state.
     e. Wait 0.4s between actions.
  3. After the push completes, broadcast 'ai_done'.

The turn is capped at 5 actions as a safety measure (normally max 3:
two moves and one push).
"""

from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING

from app.server.state_serializer import serialize_state

if TYPE_CHECKING:
    from app.server.services.broadcast_service import BroadcastService
    from app.server.session import SessionManager


class AIService:
    """Executes the AI player's turn with step-by-step broadcasting."""

    def __init__(self, session_manager: SessionManager,
                 broadcast_service: BroadcastService):
        self._sessions = session_manager
        self._broadcast = broadcast_service

    def random_ai_action(self, game) -> dict | None:
        """Pick a random valid action as a fallback when no model is loaded.

        Uses the RL environment's action space to enumerate legal actions,
        then randomly selects one.  Returns None if no actions are available.
        """
        import random
        from app.rl.env import PushFightEnv

        env = PushFightEnv()
        env.game = game
        env.current_phase = 'move' if game.can_move() else 'push'
        valid = env._get_valid_actions()
        if not valid:
            return None

        action_idx = random.choice(valid)
        phase, data = env._decode_action(action_idx)

        if phase == 'move':
            py, px, dy, dx = data
            return {'type': 'move', 'from': (py, px), 'to': (dy, dx)}
        if phase == 'push':
            py, px, direction = data
            return {'type': 'push', 'piece': (py, px), 'direction': direction}
        return None

    async def run_ai_turn(self, session_id: str) -> None:
        """Execute the AI player's full turn: up to 2 moves + 1 push.

        Each action is broadcast as a preview ('ai_action'), executed on
        the engine, then the updated state is broadcast.  Deliberate
        delays between actions allow the frontend to animate them.

        The turn ends when:
          - The AI completes a push (mandatory end of turn).
          - The game ends (someone wins).
          - No valid actions remain.
          - The safety cap of 5 actions is reached.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return

        game = session.game
        agent = session.agent

        # Brief delay before AI starts acting
        await asyncio.sleep(0.4)

        max_actions = 5  # Safety cap (normal max is 3: 2 moves + 1 push)
        for _ in range(max_actions):
            # Stop if the game is over or it's no longer the AI's turn
            if game.game_over or game.current_player != session.ai_team:
                break

            # Get next action from trained agent or random fallback
            try:
                action = (agent.get_action(game) if agent is not None
                          else self.random_ai_action(game))
            except Exception as e:
                await self._broadcast.broadcast(
                    session_id, {"event": "error", "message": str(e)})
                break

            if action is None:
                break

            # Broadcast preview so frontend can animate the intended action
            await self._broadcast.broadcast(
                session_id, {"event": "ai_action", "action": action})
            await asyncio.sleep(0.5)

            if action["type"] == "move":
                success, _msg = game.perform_move(action["from"], action["to"])
                if success:
                    await self._broadcast.broadcast_state_update(
                        session_id, serialize_state(session))
                    await asyncio.sleep(0.4)

            elif action["type"] == "push":
                py, px = action["piece"]
                direction = tuple(action["direction"])
                success = game.perform_push(py, px, direction)
                if success and not game.game_over:
                    game.switch_turn()
                await self._broadcast.broadcast_state_update(
                    session_id, serialize_state(session))
                break  # Push always ends the turn

        # Signal that the AI's turn is complete
        await self._broadcast.broadcast(session_id, {"event": "ai_done"})
