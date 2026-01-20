# Reinforcement Learning Training Guide

This guide explains how to train reinforcement learning agents for Push Fight.

## Overview

The RL system provides two interfaces:

1. **Gymnasium Environment** (`app/rl/env.py`) - Standard Gym interface for use with RL libraries
2. **Simple Agent Interface** (`app/rl/agent_interface.py`) - Direct GameState interface for custom agents

## Gymnasium Environment

### Basic Usage

```python
from app.rl import PushFightEnv

# Create environment
env = PushFightEnv()

# Reset environment
obs, info = env.reset()

# Step through environment
for _ in range(100):
    action = env.action_space.sample()  # Random action
    obs, reward, terminated, truncated, info = env.step(action)
    
    if terminated or truncated:
        obs, info = env.reset()
```

### Observation Space

The observation is a 10x4x5 array representing the board state:
- **Shape**: (10, 4, 5) - height x width x features
- **Features per cell**:
  - `[0]`: has_piece (0 or 1)
  - `[1]`: is_white (0 or 1)
  - `[2]`: is_square (0 or 1)
  - `[3]`: is_anchor (0 or 1)
  - `[4]`: is_kill_zone (0 or 1)

### Action Space

The action space is a flat discrete space with 1760 possible actions:
- **Moves** (0-1599): Encodes piece position and destination
- **Pushes** (1600-1759): Encodes piece position and direction

Actions are automatically decoded based on the current game phase (move or push).

### Reward Function

- **Win**: +1.0
- **Loss**: -1.0
- **Invalid action**: -0.1
- **Valid move/push**: 0.0 (small reward for valid actions)

## Simple Agent Interface

For agents that want to work directly with GameState:

```python
from app.rl import BaseAgent, RandomAgent
from app.engine.game_state import GameState

# Use the random agent as an example
agent = RandomAgent()

game = GameState.create_initial_game()

while not game.game_over:
    # Get action from agent
    action = agent.get_action(game)
    
    if action['type'] == 'move':
        # Execute move
        from_y, from_x = action['from']
        to_y, to_x = action['to']
        game.board.pieces[from_y][from_x] = None
        game.board.pieces[to_y][to_x] = game.board.get_piece(from_y, from_x)
        game.moves_made += 1
    elif action['type'] == 'push':
        # Execute push
        y, x = action['piece']
        direction = action['direction']
        game.perform_push(y, x, direction)
        if game.push_completed:
            game.switch_turn()
```

## Training with Stable-Baselines3

Example training script:

```python
from stable_baselines3 import PPO
from app.rl import PushFightEnv

# Create environment
env = PushFightEnv()

# Create model
model = PPO("MlpPolicy", env, verbose=1)

# Train
model.learn(total_timesteps=100000)

# Save model
model.save("push_fight_ppo")

# Test
obs, info = env.reset()
for _ in range(1000):
    action, _states = model.predict(obs)
    obs, reward, terminated, truncated, info = env.step(action)
    if terminated or truncated:
        obs, info = env.reset()
```

## Training with Custom Agents

You can create custom agents by inheriting from `BaseAgent`:

```python
from app.rl import BaseAgent
from app.engine.game_state import GameState
import random

class MyCustomAgent(BaseAgent):
    def get_action(self, game_state: GameState):
        # Your custom logic here
        valid_moves = self.get_valid_moves(game_state)
        if valid_moves:
            return {
                'type': 'move',
                'from': valid_moves[0]['from'],
                'to': valid_moves[0]['to']
            }
        
        valid_pushes = self.get_valid_pushes(game_state)
        if valid_pushes:
            push = random.choice(valid_pushes)
            return {
                'type': 'push',
                'piece': push['piece'],
                'direction': push['direction']
            }
        return None
    
    def get_observation(self, game_state: GameState):
        # Return your custom observation format
        return game_state.to_dict()
```

## Tips for Training

1. **Start Simple**: Use the random agent as a baseline
2. **Monitor Rewards**: Track win rate and average reward
3. **Action Masking**: Consider masking invalid actions to speed up training
4. **Curriculum Learning**: Start with simpler positions or shorter games
5. **Self-Play**: Train agents by playing against themselves

## Example: Two Agents Playing

```python
from app.rl import RandomAgent
from app.engine.game_state import GameState

white_agent = RandomAgent(seed=1)
brown_agent = RandomAgent(seed=2)

game = GameState.create_initial_game()

while not game.game_over:
    if game.current_player == 'white':
        agent = white_agent
    else:
        agent = brown_agent
    
    action = agent.get_action(game)
    
    if action['type'] == 'move':
        from_y, from_x = action['from']
        to_y, to_x = action['to']
        piece = game.board.get_piece(from_y, from_x)
        game.board.pieces[from_y][from_x] = None
        game.board.pieces[to_y][to_x] = piece
        game.moves_made += 1
    elif action['type'] == 'push':
        y, x = action['piece']
        direction = action['direction']
        game.perform_push(y, x, direction)
        if game.push_completed:
            game.switch_turn()

print(f"Winner: {game.winner}")
```

## Troubleshooting

### Invalid Actions

If you're getting many invalid actions, make sure to:
- Check the current game phase (move vs push)
- Validate actions before executing
- Use `get_valid_moves()` and `get_valid_pushes()` helper methods

### Environment Reset

The environment automatically handles turn switching and game phases. Make sure to reset when `terminated` or `truncated` is True.

### Observation Format

The observation is a numpy array. If you need a different format, you can modify `_get_observation()` in `PushFightEnv` or override `get_observation()` in your agent.
