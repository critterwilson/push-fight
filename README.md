# Push Fight: BJJ Edition

A digital adaptation of [Push Fight](https://www.meeplemountain.com/reviews/push-fight/) — a 2-player abstract strategy game — themed around Brazilian Jiu-Jitsu.

---

## Why I Built This

Chess gets recommended constantly as a thinking game for BJJ players. The problem is that chess rewards material accumulation and positional dominance over time — it doesn't map well to the way grappling actually works.

In 2015, I stumbled accross a game called "Push Fight". Brett Picotte was producing the game (he is apparently no longer in business), but it was the closest I could get to BJJ with my limited funds at the time. This game became one of my favorites and I always wanted to build a digital version of it.

In BJJ, position is temporary. Control is always contested. The moment you commit to a move, your opponent is already adjusting. Push Fight captures that feeling better than chess does. There's no material economy. Every piece matters. Position is everything, and the board is small enough that a single push can end the game.

I decided to add BJJ piece names (sleeve, lapel, belt, neck, joint) as a nod to the grips and positions that give control in grappling. Square pieces are the active grips that can do work; round pieces are the vital parts that one needs to protect—lose one and the match is over instantly.

---

## The Game

Push Fight is played on an irregular 10x4 board with kill zones at each end. Each player has **5 pieces**: 3 squares (attacks) and 2 rounds (vitals).

### Turn Structure

1. **Move phase** (optional): slide 0-2 of your pieces any number of squares orthogonally
2. **Push phase** (mandatory): push with one square piece — all pieces in the chain shift one square in the push direction

After pushing, an **anchor** is placed on the pushing piece, preventing the opponent from moving or pushing it or anything that in supports in a chain on the next turn.

### Pieces

| Piece | Shape | Can Push? | Losing condition |
|-------|-------|-----------|-----------------|
| Sleeve | Square | Yes | 2 squares lost = defeat |
| Lapel | Square | Yes | 2 squares lost = defeat |
| Belt | Square | Yes | 2 squares lost = defeat |
| Neck | Round | No | 1 round lost = instant defeat |
| Joint | Round | No | 1 round lost = instant defeat |

### Win Conditions

- Push an opponent's **Neck** or **Joint** off the board
- Push **2 of the opponent's square pieces** off the board
- Opponent has **no legal push** at the start of their turn

### Board Coordinate System

Columns A-D run top to bottom (4 rows). Rows 1-10 run left to right (10 columns). Kill zones are the leftmost and rightmost columns, plus several irregular corner cells.

```
   1   2   3   4   5 | 6   7   8   9  10
A  X   X   .   .   W | B   .   X   X   X
B  X   .   .   W   W | B   B   .   .   X
C  X   .   .   .   W | B   .   .   .   X
D  X   X   X   .   W | B   .   .   X   X
                  ^ centre line (dashed)
```

White starts on the left (rows 1-5), Black on the right (rows 6-10).

---

## Architecture

```
+-------------------------------------------------------------+
|  Browser                                                     |
|  React + Vite (SVG board, voice control, RAG chat panel)    |
+-----------------------+-------------------------------------+
                        | REST + WebSocket (/ws/{id})
+-----------------------v-------------------------------------+
|  FastAPI  --  port 8000                                      |
|  Routes -> Handlers -> Services (3-layer architecture)      |
+--------+---------------------+------------------------------+
         |                     |
+--------v--------+  +---------v-----------+  +---------------+
|  engine/        |  |  rl/  (AI)          |  |  rag/         |
|  Core game      |  |  MaskablePPO        |  |  LangChain +  |
|  logic          |  |  self-play agent    |  |  ChromaDB +   |
+-----------------+  +---------------------+  |  Ollama       |
                                              +---------------+
```

The system has six backend modules:

| Module | What it does | README |
|--------|-------------|--------|
| `app/engine/` | Board, pieces, game rules, win conditions | [engine/README.md](app/engine/README.md) |
| `app/server/` | FastAPI REST + WebSocket API, 3-layer architecture | [server/README.md](app/server/README.md) |
| `app/rl/` | MaskablePPO training, self-play, difficulty presets | [rl/README.md](app/rl/README.md) |
| `app/rag/` | RAG referee — LangChain, ChromaDB, Ollama | [rag/README.md](app/rag/README.md) |
| `app/storage/` | Save / load game state to JSON | [storage/README.md](app/storage/README.md) |
| `app/pygame_ui/` | Legacy PyGame desktop UI (local only) | [pygame_ui/README.md](app/pygame_ui/README.md) |

### Server Architecture

The FastAPI server follows a 3-layer separation of concerns:

```
Routes (API endpoint definitions)
  -> Handlers (HTTP translation, error mapping, response formatting)
    -> Services (pure business logic, no HTTP dependencies)
```

| Layer | Responsibility | Example |
|-------|---------------|---------|
| **Routes** | Define APIRouter endpoints, path/query params | `routes/game_routes.py` |
| **Handlers** | Catch `ValueError` -> `HTTPException`, serialize state, kick off async tasks | `handlers/game_handler.py` |
| **Services** | Game engine calls, WebSocket broadcast, AI turns, save/load | `services/game_service.py` |

Dependencies are wired via constructor injection in `main.py` (the composition root).

### RAG Referee System

The in-game AI referee answers rule questions using Retrieval-Augmented Generation:

```
User question
  -> embed with nomic-embed-text
  -> find top-5 similar rule chunks in ChromaDB
  -> assemble prompt (system template + chunks + game state + question)
  -> generate answer with Ollama LLM (temperature=0, max 300 tokens)
  -> WebSocket rag_answer event -> frontend chat panel
```

**Models used:**
- `nomic-embed-text` — converts text into vectors for semantic search
- `llama3` (default) — generates natural-language answers grounded in the retrieved rules

**Game state context** includes: current phase, moves remaining, anchor position, full piece inventory with coordinates, eliminations, and recent actions.

### Benchmark System

The `benchmark/` directory contains tools for evaluating Ollama model quality:

- `benchmark_models.py` — tests models against 18 game-state-specific questions across 6 scenarios
- `dashboard.html` — standalone HTML dashboard for visualizing benchmark results
- `benchmark_results.json` — latest benchmark output

Scoring dimensions: keyword relevance (30%), factual correctness (35%), hallucination detection (25%), conciseness (10%).

```bash
# Run all installed models
python benchmark/benchmark_models.py

# Quick test with a specific model
python benchmark/benchmark_models.py --models llama3 --quick

# Pull missing models before testing
python benchmark/benchmark_models.py --pull
```

### Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, SVG |
| Backend | FastAPI, uvicorn, WebSockets |
| AI opponent | MaskablePPO (sb3-contrib), PyTorch |
| RAG referee | LangChain, ChromaDB, Ollama (llama3 + nomic-embed-text) |
| Container | Docker multi-stage (Node 22 -> Python 3.13-slim) |
| Orchestration | Kubernetes + Istio (via UDS Core) |
| Packaging | Zarf + UDS Bundle |

---

## Installation

### Prerequisites

| Dependency | Version | Purpose |
|-----------|---------|---------|
| Python | 3.13+ | Backend runtime |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | latest | Python package manager |
| Node.js | 22+ | Frontend build toolchain |
| npm | (bundled with Node) | Frontend package manager |
| [Ollama](https://ollama.com/download) | latest | Local LLM inference (for RAG referee) |

### Step 1: Clone the Repository

```bash
git clone https://github.com/critterwilson/push-fight-app.git
cd push-fight-app
```

### Step 2: Install Python Dependencies

[uv](https://docs.astral.sh/uv/getting-started/installation/) manages the Python environment and dependencies. If you don't have it:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv
```

Then install the project:

```bash
uv sync --dev
```

This creates a `.venv/` directory, installs Python 3.13 if needed, and installs all dependencies from `pyproject.toml`.

### Step 3: Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### Step 4: Install Ollama and Pull Models

The RAG referee requires [Ollama](https://ollama.com/download) running locally with two models:

```bash
# Install Ollama (macOS)
brew install ollama

# Or download from https://ollama.com/download

# Start the Ollama server (runs on port 11434)
ollama serve
```

In a separate terminal, pull the required models:

```bash
# LLM for generating answers (~4.7 GB)
ollama pull llama3

# Embedding model for semantic search (~274 MB)
ollama pull nomic-embed-text
```

> **Note:** Ollama and its models are only required for the RAG referee feature (the in-game chat panel that answers rule questions). The game itself works without Ollama — you just won't be able to ask the AI referee questions.

### Step 5: Verify Installation

```bash
# Run backend tests (should see 160+ pass, with a few pre-existing RL env skips)
uv run pytest tests/

# Run frontend tests
cd frontend && npm test && cd ..

# Verify Ollama is reachable
curl http://localhost:11434/api/tags
```

---

## Running Locally

### Quick Start with tmuxinator

A `.tmuxinator.yml` config is included in the repo for one-command local dev. It launches the FastAPI backend and Vite frontend in side-by-side tmux panes.

```bash
# Requires tmux + tmuxinator (brew install tmux tmuxinator)
tmuxinator start -p .tmuxinator.yml
```

This starts:
- **Left pane:** `uv run uvicorn app.server.main:app --reload --port 8000`
- **Right pane:** `cd frontend && npm run dev`

### Manual Start

**Terminal 1 — Backend (port 8000):**

```bash
uv run uvicorn app.server.main:app --reload --port 8000
```

**Terminal 2 — Frontend (port 3000):**

```bash
cd frontend
npm run dev
```

Open **http://localhost:3000** in your browser. The Vite dev server proxies `/api` and `/ws` requests to `http://localhost:8000`.

### Running Tests

```bash
# Backend (pytest)
uv run pytest tests/

# Frontend (vitest + jsdom)
cd frontend && npm test
```

### Legacy PyGame UI

A standalone desktop UI is available for local play without a browser:

```bash
uv run python -m app.pygame_ui.main
```

---

## Environment Variables

All environment variables have sensible defaults for local development. Only set these when deploying to Kubernetes or changing service locations.

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama LLM server URL |
| `CHROMA_HOST` | *(unset — uses local SQLite)* | ChromaDB server hostname (enables remote HTTP mode) |
| `CHROMA_PORT` | `8000` | ChromaDB server port (only used when `CHROMA_HOST` is set) |

**Local development:** No env vars needed. ChromaDB runs in-process using SQLite (persisted to `./chroma_db/`), and Ollama is expected at `localhost:11434`.

**Kubernetes:** Set `OLLAMA_HOST=http://ollama:11434` and `CHROMA_HOST=chromadb` in `deployment.yaml` to point at the in-cluster services.

---

## UI Features

### Voice Control

Toggle the microphone with the **Mic On/Off** button (supported browsers only). Commands:

```
"sleeve to b4"      — move your Sleeve to row B, column 4
"lapel push down"   — push with Lapel toward column 10
"skip"              — end move phase and go to push
```

### Board Orientation

The SVG board renders landscape (rows left to right, columns top to bottom). The coordinate transposition is entirely in the frontend — the engine coordinate system `(y=row, x=col)` is unchanged.

### BJJ Theme

Colors use a Brazilian Jiu-Jitsu belt palette (`--belt-white`, `--belt-blue`, `--belt-purple`, `--belt-brown`, `--belt-black`). Light and dark mode are toggled via the header button.

---

## Docker

The app uses a multi-stage Docker build:

1. **Stage 1** (Node 22): builds the React frontend (`npm ci && npm run build`)
2. **Stage 2** (Python 3.13-slim): installs Python deps, copies app source + built frontend, runs as non-root user (UID 1001)

```bash
# Build the image
docker build -t push-fight-app:latest .

# Run locally (game only — no Ollama/ChromaDB)
docker run -p 8000:8000 push-fight-app:latest
```

The container exposes port 8000 and includes a health check at `GET /health`.

---

## UDS Deployment

The app is packaged with [Zarf](https://zarf.dev) and deployed via a [UDS Bundle](https://github.com/defenseunicorns/uds-cli) that includes k3d, Zarf init, UDS Core (Istio + Pepr + Keycloak), and the Push Fight app.

```bash
docker build -t push-fight-app:latest .
zarf package create .
uds create .
uds deploy uds-bundle.yaml
```

The UDS bundle deploys three services into the `push-fight` namespace:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| push-fight-app | `push-fight-app:latest` | 8000 | Game server + static frontend |
| chromadb | `chromadb/chroma:latest` | 8000 | Vector database for RAG |
| ollama | `ollama/ollama:latest` | 11434 | LLM inference for RAG referee |

After deploy: `https://push-fight.uds.dev`

---

## RL Training

Train the AI opponent using self-play with MaskablePPO:

```bash
# Full training run (default 1M timesteps, 8 parallel envs)
python -m app.rl.train --train --timesteps 1000000 --no-render

# Quick smoke test
python -m app.rl.train --train --no-selfplay --n-envs 1 --timesteps 5000

# Resume from checkpoint
python -m app.rl.train --train --resume models/checkpoints/rl_model_500000_steps.zip
```

Pre-trained models at three difficulty levels are included in `models/` (easy, medium, hard).

---

---

Built and deployed with [Unicorn Delivery Service (UDS)](https://uds.defenseunicorns.com/) by Defense Unicorns.
