# Push Fight App

A full-stack Push Fight board game with a React/FastAPI web interface, a Reinforcement Learning AI opponent (MaskablePPO), and a RAG-powered referee that answers rules questions in plain English. Designed for deployment on [UDS](https://github.com/defenseunicorns/uds-core) (Unicorn Delivery Service).

## Game Rules

Push Fight is a 2-player abstract strategy game on an irregular 10×4 board with kill zones at the top/bottom edges.

- Each team has **3 square pieces** (pushers) and **2 round pieces** (blockers)
- On a turn, a player may make **0–2 slides** (move any own piece via BFS to a reachable empty square), then **must** make exactly **1 push** with a square piece
- A push moves a chain of pieces one cell in an orthogonal direction; pieces pushed into kill zones are eliminated
- After pushing, an **anchor** is placed at the pusher's new position to prevent the opponent from reversing the push
- **Lose condition:** 2 of your squares eliminated, OR 1 of your rounds eliminated, OR no legal push available

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser                                                     │
│  React + Vite (SVG board, chat panel, game controls)        │
└───────────────────┬─────────────────────────────────────────┘
                    │ REST + WebSocket (/ws/{id})
┌───────────────────▼─────────────────────────────────────────┐
│  FastAPI (app/server/)   — port 8000                        │
│  • Session management (multiple concurrent games)           │
│  • Serves built React app as static files                   │
│  • WebSocket pushes AI moves + RAG answers to client        │
└──────┬─────────────────────┬───────────────────────────────-┘
       │                     │
┌──────▼──────┐    ┌─────────▼──────────┐
│  app/engine │    │  app/rl  (AI)       │
│  Core game  │    │  MaskablePPO agent  │
│  logic      │    │  (sb3-contrib)      │
└─────────────┘    └────────────────────┘
       │
┌──────▼─────────────────────────────────────────────────────-┐
│  app/rag/  — RAG Referee                                    │
│  LangChain + ChromaDB (vectors) + Ollama (LLM inference)   │
└─────────────────────────────────────────────────────────────┘
```

### Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, SVG |
| Backend | FastAPI, uvicorn, WebSockets |
| AI opponent | MaskablePPO (sb3-contrib), PyTorch |
| RAG referee | LangChain, ChromaDB, Ollama (llama3 + nomic-embed-text) |
| Container | Docker multi-stage (Node 22 → Python 3.13-slim) |
| Orchestration | Kubernetes + Istio (via UDS Core) |
| Packaging | Zarf + UDS Bundle |

---

## Project Structure

```
app/
  engine/              # Core game logic (board, pieces, game state)
    board.py           # 10×4 board, BFS movement, push chains, kill zones
    game_state.py      # Turn flow, push execution, win conditions, anchor
    pieces.py          # Piece class (team: white/black, shape: square/round)
  server/              # FastAPI web server
    main.py            # App entry point: all REST routes + WebSocket
    session.py         # GameSession dataclass + SessionManager
    models.py          # Pydantic request/response models
    state_serializer.py # game state → frontend JSON
  rl/                  # Reinforcement learning
    env.py             # Gymnasium environment (PushFightEnv)
    agent.py           # Shared AI Agent class for inference
    train.py           # Training script (MaskablePPO)
    play_against_ai.py # CLI to play against trained model
  rag/                 # RAG referee (LLM + vector DB)
  pygame_ui/           # Legacy PyGame UI (local play only)
  cli.py               # CLI utilities
frontend/
  src/
    App.jsx            # Layout, New Game modal, board legend
    Board.jsx          # SVG board: pieces, kill zones, push arrows
    StatusBar.jsx      # Turn/phase display, pieces lost
    GameControls.jsx   # Skip-moves, direction pad, save/load
    ChatPanel.jsx      # RAG referee chat panel
    useGame.js         # Game state hook (REST + WebSocket, auto-reconnect)
    api.js             # All REST calls with error handling
    ErrorBoundary.jsx  # Render error boundary with reset button
    tests/             # 33 frontend tests (Vitest)
assets/
  rules.md             # Rulebook (indexed into ChromaDB for RAG)
models/                # Saved trained RL models (.zip)
tests/                 # Python tests (pytest)
deployment.yaml        # K8s Namespace, Deployments, Services
network-policies.yaml  # K8s NetworkPolicies (default-deny + allow rules)
uds-package.yaml       # UDS Package CRD (Istio VirtualService, network allows)
zarf.yaml              # Zarf package manifest
uds-bundle.yaml        # UDS Bundle (k3d + Zarf init + UDS Core + app)
Dockerfile             # Multi-stage build
```

---

## Local Development

### Prerequisites

- Python 3.13+ with [uv](https://github.com/astral-sh/uv)
- Node 22+ with npm

### Backend

```bash
# Install dependencies
uv sync --dev

# Start FastAPI server (hot-reload)
uv run uvicorn app.server.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

The Vite dev server proxies `/api` and `/ws` to `http://localhost:8000`.

### Start both with tmuxinator

```bash
# .tmuxinator.yml is in .gitignore — not committed or deployed
tmuxinator start -p .tmuxinator.yml
```

### Legacy PyGame UI (local only)

```bash
uv run python -m app.pygame_ui.main
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health/readiness probe |
| `POST` | `/api/game` | Create new game (`mode`: PvP/PvAI, `difficulty`) |
| `GET` | `/api/game/{id}` | Get full game state as JSON |
| `POST` | `/api/game/{id}/move` | Make a slide move |
| `POST` | `/api/game/{id}/push` | Make a push |
| `POST` | `/api/game/{id}/ask` | Submit a RAG referee question (answer via WebSocket) |
| `POST` | `/api/game/{id}/save` | Persist game to disk |
| `GET` | `/api/game/{id}/load` | Restore game from disk |
| `WS` | `/ws/{id}` | Real-time updates: AI moves, RAG answers, game over |

---

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

# CLI play against AI
uv run python -m app.rl.play_against_ai --model models/push_fight_ppo
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

- **Observation space:** 203 features — 10×4×5 per-cell features (`has_piece`, `is_mine`, `is_square`, `is_anchor`, `is_kill_zone`) + 3 scalars (`phase`, `moves_remaining`, `is_white_turn`)
- **Action space:** Discrete(1760) — 1600 move actions + 160 push actions
- **Action masking:** Only valid actions available each step
- **Rewards:** Win +1.0, Loss -1.0, push opponent toward kill zone +0.05, invalid action substitution -0.05
- **Episode limit:** 300 steps
- **Hyperparameters:** n_steps=4096, batch_size=128, gamma=0.995, ent_coef=0.02

---

## Testing

```bash
# Python — all tests (engine + RL + server + RAG)
uv run pytest

# Specific suites
uv run pytest tests/test_engine.py     # 71 engine tests
uv run pytest tests/test_rl_env.py    # 25 RL environment tests
uv run pytest tests/test_agent.py     # AI agent tests
uv run pytest tests/test_logging.py   # game logging tests

# Frontend — 33 tests (Vitest)
cd frontend && npm test
```

---

## UDS Deployment

The app is packaged with [Zarf](https://zarf.dev) and deployed via a [UDS Bundle](https://github.com/defenseunicorns/uds-cli) that includes k3d, Zarf init, UDS Core (Istio + Pepr + Keycloak), and the Push Fight app.

### Prerequisites

- [`docker`](https://docs.docker.com/get-docker/)
- [`zarf`](https://docs.zarf.dev/getting-started/install)
- [`uds`](https://github.com/defenseunicorns/uds-cli#installation) CLI
- [`kubectl`](https://kubernetes.io/docs/tasks/tools/)

### 1. Build the container image

```bash
docker build -t push-fight-app:latest .
```

The Dockerfile uses a two-stage build:
1. **Stage 1 (Node 22):** `npm ci && npm run build` — produces `frontend/dist/`
2. **Stage 2 (Python 3.13-slim):** installs Python deps, copies `app/`, `assets/`, `models/`, and `frontend/dist/`. FastAPI serves the React build at `/` via `StaticFiles`.

### 2. Create the Zarf package

```bash
zarf package create .
```

This bundles the container images (`push-fight-app:latest`, `chromadb/chroma:latest`, `ollama/ollama:latest`) and the manifests (`deployment.yaml`, `network-policies.yaml`, `uds-package.yaml`) into a Zarf package tarball.

### 3. Deploy via UDS Bundle

```bash
uds deploy uds-bundle.yaml
```

The bundle deploys in order:
1. **uds-k3d** — local k3d cluster
2. **init** — Zarf init package (container registry, etc.)
3. **core** — UDS Core (Istio, Pepr, Keycloak, Prometheus, Grafana, …)
4. **push-fight-app** — the Push Fight Zarf package

After deploy, Zarf automatically:
- Waits for ChromaDB and Ollama deployments to become available
- Pulls `llama3` into the Ollama pod (`kubectl exec … ollama pull llama3`)
- Pulls `nomic-embed-text` for embeddings
- Waits for the Push Fight app deployment to become available

### Kubernetes resources deployed

| Resource | Description |
|----------|-------------|
| `Namespace: push-fight` | Istio injection enabled |
| `Deployment: push-fight-app` | FastAPI + React; liveness/readiness on `GET /health` |
| `Deployment: chromadb` | ChromaDB vector store for RAG |
| `Deployment: ollama` | Ollama LLM inference (llama3 + nomic-embed-text) |
| `Service: push-fight-app` | ClusterIP on port 8000 |
| `Service: chromadb` | ClusterIP on port 8000 |
| `Service: ollama` | ClusterIP on port 11434 |
| `UDSPackage: push-fight` | Processed by Pepr to create Istio VirtualService + AuthorizationPolicies |
| NetworkPolicies | Default-deny-all + targeted allow rules |

### Environment variables (set in deployment.yaml)

| Variable | Value | Description |
|----------|-------|-------------|
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama service URL |
| `CHROMA_HOST` | `chromadb` | ChromaDB service hostname |
| `CHROMA_PORT` | `8000` | ChromaDB service port |

### Accessing the app

After a successful deploy the app is available at:

```
https://push-fight.<uds-domain>
```

The UDS Core tenant Istio gateway routes traffic to `push-fight-app:8000`. WebSocket connections to `/ws/{id}` are handled automatically by Istio (HTTP/1.1 Upgrade).

> **Default UDS dev domain:** `push-fight.uds.dev`

### Networking (UDS Package)

The `uds-package.yaml` is processed by Pepr and creates:

- **Istio VirtualService:** `push-fight.<domain>` → `push-fight-app:8000` (tenant gateway, HTTPS)
- **Network allow rules** (translated to Cilium / K8s NetworkPolicies):
  - Ingress: Istio tenant gateway → app (port 8000)
  - Egress: app → ChromaDB (port 8000)
  - Egress: app → Ollama (port 11434)
  - Egress: app → kube-dns

### Persistence

Game saves are stored in `/app/saves` inside the pod, backed by an `emptyDir` volume (lost on pod restart). To persist saves across restarts, replace the `emptyDir` with a PVC in `deployment.yaml`:

```yaml
volumes:
- name: saves
  persistentVolumeClaim:
    claimName: push-fight-saves
```

### Health probes

| Probe | Endpoint | Initial delay | Period |
|-------|----------|--------------|--------|
| Liveness | `GET /health` | 60 s | 30 s |
| Readiness | `GET /health` | 15 s | 10 s |

---

## Key Design Decisions

- Teams are `'white'` and `'black'` (not 'brown') throughout the codebase
- The RL env uses `is_mine` (relative to current player) rather than absolute team encoding, so the single policy generalizes across both sides
- Push validation uses `_is_valid_push()` to check legality without mutating game state, then executes once via `perform_push()`
- Micro-rewards for individual moves were removed — only win/loss and kill-zone proximity shaping remain to keep the reward signal clean
- The container runs as non-root UID 1001 for security
- `.dockerignore` excludes `.venv/`, `frontend/node_modules/`, `chroma_db/`, and `saves/` to keep the image lean
