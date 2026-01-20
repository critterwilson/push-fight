# Development Guide

## Local Development Setup

### Prerequisites

- Python 3.13+ with `uv` package manager
- PyGame 2.5.0+ (for GUI)
- Gymnasium 0.29.0+ (for RL training)

### Installation

```bash
# Install dependencies
uv sync

# Or install with dev dependencies
uv sync --dev
```

### Running the Game

The game can be run in three modes:

#### 1. PyGame UI (Recommended)

Launch the graphical interface:

```bash
uv run python -m app.main --pygame
# or simply:
uv run python -m app.main
```

This opens a PyGame window where you can play the game with mouse and keyboard.

#### 2. CLI Mode (Quick Testing)

Run the command-line interface:

```bash
uv run python -m app.cli
```

Useful for quick game logic testing without GUI overhead.

#### 3. Web API Mode

Start the Flask API server:

```bash
uv run python -m app.main --web --port 5001
```

The Flask API will be available at `http://localhost:5001`
API endpoints are at `http://localhost:5001/api/`

**Note:** Port 5001 is used instead of 5000 to avoid conflicts with macOS AirPlay Receiver.

### Development Workflow

1. **Game Engine**: Located in `app/engine/` - core game logic
2. **PyGame UI**: Located in `app/pygame_ui/` - graphical interface
3. **CLI**: Located in `app/cli.py` - command-line interface
4. **RL System**: Located in `app/rl/` - reinforcement learning infrastructure

### Testing

#### Backend Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html
```

### RL Training

See [RL_TRAINING.md](RL_TRAINING.md) for detailed instructions on training reinforcement learning agents.

### Troubleshooting

#### Module Not Found Errors

- Ensure you're using `uv run python -m app.main` (not just `python`)
- Check that all dependencies are installed: `uv sync`

#### PyGame Issues

- Ensure PyGame is installed: `uv add pygame`
- On Linux, you may need additional system packages for PyGame

#### Port Already in Use

If port 5001 is already in use:

```bash
uv run python -m app.main --web --port 5002
```
