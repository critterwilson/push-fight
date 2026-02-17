# Push Fight App

A Push Fight board game implementation with PyGame UI and RL training via MaskablePPO.

## Game Rules

Push Fight is a 2-player abstract strategy game on an irregular 10x4 board with kill zones at the top/bottom edges.

- Each team has **3 square pieces** (pushers) and **2 round pieces** (blockers)
- On a turn, a player may make **0-2 slides** (move any own piece via BFS to a reachable empty square), then **must** make exactly **1 push** with a square piece
- A push moves a chain of pieces one cell in an orthogonal direction; pieces pushed into kill zones are eliminated
- After pushing, an **anchor** is placed at the pusher's new position to prevent the opponent from reversing the push
- **Lose condition:** 2 of your squares eliminated, OR 1 of your rounds eliminated, OR no legal push available

## Project Structure

```
app/
  engine/          # Core game logic (board, pieces, game state)
    board.py       # 10x4 board, BFS movement, push chains, kill zones
    game_state.py  # Turn flow, push execution, win conditions, anchor
    pieces.py      # Piece class (team: white/black, shape: square/round)
  pygame_ui/       # PyGame graphical interface
    main.py        # Entry point for PyGame UI
    game_view.py   # Main game view (PvP and PvCPU modes)
    board_renderer.py
    input_handler.py
    ui_components.py
  rl/              # Reinforcement learning
    env.py         # Gymnasium environment (PushFightEnv)
    agent.py       # Shared AI Agent class for inference
    train.py       # Training script (MaskablePPO)
    play_against_ai.py  # CLI to play against trained model
  cli.py           # CLI utilities (board printing, input parsing)
tests/
  test_engine.py   # 71 engine tests
  test_rl_env.py   # 25 RL environment tests
  test_logging.py  # Tests for game logging
  test_agent.py    # Tests for AI agent
models/            # Saved trained models (.zip files)
game_logs/         # JSON logs of played games
```

## Running the Game

```bash
# PyGame UI
uv run python -m app.pygame_ui.main

# CLI play against AI
uv run python -m app.rl.play_against_ai --model models/push_fight_ppo
```

## RL Training

Uses **MaskablePPO** from `sb3-contrib` with action masking. The agent plays both sides (self-play with a single policy).

### Quick Start

```bash
# Train a model (saved to models/ by default)
uv run python -m app.rl.train --train --timesteps 500000 --no-render

# Train with periodic visualization
uv run python -m app.rl.train --train --timesteps 50000 --render-every 1000

# Watch a trained model play
uv run python -m app.rl.train --watch --model models/push_fight_ppo --episodes 5
```

### Training Options

| Option | Description |
|--------|-------------|
| `--train` | Train a new model |
| `--watch` | Watch a saved model play |
| `--timesteps N` | Training steps (default: 100000) |
| `--model PATH` | Model path to save/load (default: `models/push_fight_ppo`) |
| `--render-every N` | Show a game every N steps while training (default: 1000) |
| `--render-delay S` | Seconds between rendered moves (default: 0.3) |
| `--fast` | No delays, minimal output |
| `--no-render` | Headless training (faster) |
| `--device DEVICE` | `auto`, `cuda`, `mps`, or `cpu` (default: auto) |

### RL Environment Details

- **Observation space:** 203 features — 10x4x5 per-cell features (has_piece, is_mine, is_square, is_anchor, is_kill_zone) + 3 scalars (phase, moves_remaining, is_white_turn)
- **Action space:** Discrete(1760) — 1600 move actions + 160 push actions
- **Action masking:** Only valid actions are available to the agent each step
- **Rewards:** Win +1.0, Loss -1.0, push opponent toward kill zone +0.05, invalid action substitution -0.05
- **Episode limit:** 300 steps
- **Hyperparameters:** n_steps=4096, batch_size=128, gamma=0.995, ent_coef=0.02

## Development

```bash
# Install dependencies
uv sync --dev

# Run all tests (96 total)
uv run pytest

# Run engine tests only
uv run pytest tests/test_engine.py

# Run RL env tests only
uv run pytest tests/test_rl_env.py
```

## Key Design Decisions

- Teams are `'white'` and `'black'` (not 'brown') throughout the codebase
- The RL env uses `is_mine` (relative to current player) rather than absolute team encoding, so the single policy generalizes across both sides
- Push validation uses `_is_valid_push()` to check legality without mutating game state, then executes once via `perform_push()`
- Micro-rewards for individual moves were removed — only win/loss and kill-zone proximity shaping remain to keep the reward signal clean
