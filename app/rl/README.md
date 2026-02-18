# RL — Reinforcement Learning Agent

Trains a **MaskablePPO** policy (from `sb3-contrib`) to play Push Fight. Action masking ensures the agent only considers legal moves at each step, which dramatically speeds up learning in a game with many illegal actions.

## Files

| File | Purpose |
|------|---------|
| `env.py` | Gymnasium environments: `PushFightEnv` (both sides) + `SelfPlayEnv` (agent=white, opponent auto-plays black) |
| `agent.py` | `Agent` class — loads a saved model and exposes `get_action(game)` for the server |
| `train.py` | Training script: self-play, checkpointing, difficulty presets |
| `play_against_ai.py` | CLI to play interactively against a trained model |

---

## Quick Start

```bash
# Train (1M steps, self-play, saves to models/)
uv run python -m app.rl.train --train --timesteps 1000000 --no-render

# Smoke test (fast, no self-play, 5k steps)
uv run python -m app.rl.train --train --no-selfplay --n-envs 1 --timesteps 5000

# Resume training from a checkpoint
uv run python -m app.rl.train --train --resume models/push_fight_ppo --timesteps 500000

# Watch a trained model play
uv run python -m app.rl.train --watch --model models/push_fight_ppo --episodes 5

# Play against the AI in the terminal
uv run python -m app.rl.play_against_ai --model models/push_fight_ppo
```

---

## Observation Space (205 features)

| Slice | Size | Contents |
|-------|------|---------|
| Board features | 200 (10×4×5) | `has_piece`, `is_mine`, `is_square`, `is_anchor`, `is_kill_zone` per cell |
| Scalar features | 5 | `is_push_phase`, `moves_remaining`, `is_white_turn`, `is_setup_phase`, `pieces_placed_fraction` |

`is_mine` encodes pieces relative to the current player rather than absolute team — this lets a single policy generalize to both sides.

---

## Action Space (Discrete 1800)

| Range | Count | Encoding |
|-------|-------|---------|
| Move actions | 1600 (0–1599) | `piece_y × 160 + piece_x × 40 + dest_y × 4 + dest_x` |
| Push actions | 160 (1600–1759) | `1600 + piece_y × 16 + piece_x × 4 + direction_idx` |
| Placement actions | 40 (1760–1799) | `1760 + y × 4 + x` (used only during setup phase) |

Action masking zeroes out all illegal actions before sampling, so the agent never wastes gradient on impossible moves.

---

## Reward Shaping

| Signal | Value |
|--------|-------|
| Win | +1.0 |
| Loss | −1.0 |
| Edge proximity (per step) | ±`EDGE_REWARD_SCALE` × weighted sum |

The edge proximity reward pushes the agent toward getting opponent pieces close to the board boundary (and its own pieces away). It is computed from the **current player's perspective before `switch_turn()`**:
- Round pieces weight = 1.0 (losing a round = instant loss)
- Square pieces weight = 0.5

`EDGE_REWARD_SCALE = 0.005` keeps shaping small so win/loss still dominates.

Episode length limit: **300 steps**.

---

## Self-Play

`SelfPlayEnv` wraps `PushFightEnv`. The agent always plays white; black is controlled by a frozen snapshot loaded from `models/pool/`. At each episode reset, `_reload_opponent()` picks a random snapshot from the pool so the agent faces a curriculum of increasingly strong opponents.

`SelfPlayCallback` in `train.py` saves a snapshot every 50k steps.

---

## Training Hyperparameters

| Parameter | Value |
|-----------|-------|
| Algorithm | MaskablePPO |
| Network | `[256, 256, 128]` |
| Learning rate | 3e-4 → 1e-5 (linear decay) |
| `n_steps` | 4096 |
| `batch_size` | 128 |
| `gamma` | 0.995 |
| `ent_coef` | 0.02 |
| Parallel envs | 8 × SubprocVecEnv |

---

## Difficulty Presets

| Preset | Timesteps | Random action % | Saved to |
|--------|-----------|-----------------|---------|
| `easy` | 500k | 50% | `models/easy` |
| `medium` | 1M | 20% | `models/medium` |
| `hard` | 2M | 5% | `models/hard` |

Each preset bootstraps from the previous tier's weights.

```bash
uv run python -m app.rl.train --difficulty easy
uv run python -m app.rl.train --difficulty medium
uv run python -m app.rl.train --difficulty hard
```

---

## Training CLI Flags

| Flag | Description |
|------|-------------|
| `--train` | Train a new model |
| `--watch` | Watch a saved model play |
| `--timesteps N` | Training steps (default: 1 000 000) |
| `--model PATH` | Model path to save/load |
| `--no-render` | Headless training (faster) |
| `--no-selfplay` | Use plain `PushFightEnv` instead of `SelfPlayEnv` |
| `--n-envs N` | Number of parallel environments |
| `--resume PATH` | Continue training from checkpoint |
| `--device DEVICE` | `auto`, `cuda`, `mps`, or `cpu` |
| `--difficulty PRESET` | `easy`, `medium`, or `hard` |
