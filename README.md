# Push Fight: BJJ Edition

A full-stack Push Fight board game with a React/FastAPI web interface, BJJ-themed pieces and voice control, a Reinforcement Learning AI opponent (MaskablePPO), and a RAG-powered referee that answers rules questions in plain English. Designed for deployment on [UDS](https://github.com/defenseunicorns/uds-core) (Unicorn Delivery Service).

---

## Game Rules

Push Fight is a 2-player abstract strategy game on an irregular 10×4 board with kill zones at the left and right edges (rows 1 and 10, plus irregular corner cells).

### Pieces

Each team has **5 BJJ-named pieces** — 3 square (pushers) and 2 round (blockers):

| Piece | Shape | Role | Defeat condition |
|-------|-------|------|-----------------|
| Sleeve | Square | Can move and push | Need 2 squares lost to lose |
| Lapel | Square | Can move and push | Need 2 squares lost to lose |
| Belt | Square | Can move and push | Need 2 squares lost to lose |
| Choke | Round | Can move, cannot push | Lose 1 = instant loss |
| Lock | Round | Can move, cannot push | Lose 1 = instant loss |

### Turn Structure

1. **Move phase** (optional): slide 0–2 of your own pieces any number of empty squares orthogonally
2. **Push phase** (mandatory): push with one of your square pieces into an adjacent occupied cell; all pieces in the chain shift one square in the push direction

After pushing, an **anchor** is placed on the pushing piece, preventing the opponent from moving or pushing it on their next turn.

### Win Conditions

- Push an opponent's **Choke** or **Lock** off the board
- Push **2 of the opponent's square pieces** off the board (any combination of Sleeve/Lapel/Belt)
- Opponent has **no legal push** at the start of their turn

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
└──────┬─────────────────────┬────────────────────────────────┘
       │                     │
┌──────▼──────┐    ┌─────────▼──────────┐
│  app/engine │    │  app/rl  (AI)       │
│  Core game  │    │  MaskablePPO agent  │
│  logic      │    │  (sb3-contrib)      │
└─────────────┘    └────────────────────┘
       │
┌──────▼─────────────────────────────────────────────────────┐
│  app/rag/  — RAG Referee                                   │
│  LangChain + ChromaDB (vectors) + Ollama (LLM inference)  │
└────────────────────────────────────────────────────────────┘
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
    pieces.py          # Piece class (team: white/black, shape: square/round, name: BJJ name)
  server/              # FastAPI web server
    main.py            # App entry point: all REST routes + WebSocket
    session.py         # GameSession dataclass + SessionManager
    models.py          # Pydantic request/response models
    state_serializer.py # game state → frontend JSON (includes piece names)
  rl/                  # Reinforcement learning
    env.py             # Gymnasium environment (PushFightEnv)
    agent.py           # Shared AI Agent class for inference
    train.py           # Training script (MaskablePPO)
    play_against_ai.py # CLI to play against trained model
  rag/                 # RAG referee (LLM + vector DB)
  storage/             # Game save/load utilities
  pygame_ui/           # Legacy PyGame UI (local play only)
frontend/
  src/
    App.jsx            # Layout, New Game modal, board legend, footer
    Board.jsx          # SVG board: landscape orientation, pieces, kill zones, push arrows
    StatusBar.jsx      # Turn/phase display, pieces lost
    GameControls.jsx   # Skip-moves, direction pad, save/load
    ChatPanel.jsx      # RAG referee chat panel
    ThemeToggle.jsx    # Light/dark mode toggle
    useGame.js         # Game state hook (REST + WebSocket, auto-reconnect)
    useVoiceControl.js # Web Speech API voice command handler
    api.js             # All REST calls with error handling
    ErrorBoundary.jsx  # Render error boundary with reset button
    tests/             # 61 frontend tests (Vitest + jsdom)
  public/
    doug.svg           # Unicorn Delivery Service mascot (footer)
assets/
  rules.md             # BJJ-themed rulebook (RAG-optimized for MarkdownHeaderTextSplitter)
  doug.svg             # UDS mascot source
tests/                 # Python tests (pytest) — 122 tests
  test_engine.py       # Engine: board, movement, push chains, win conditions
  test_server.py       # FastAPI routes + WebSocket behavior
  test_integration.py  # End-to-end game flow
  test_rl_env.py       # RL environment (observation, action masking)
  test_agent.py        # AI agent inference
  test_logging.py      # Game logging
  test_storage.py      # Save/load round-trips
  test_state_formatter.py # State serializer (piece names, board layout)
deployment.yaml        # K8s Namespace, Deployments, Services
network-policies.yaml  # K8s NetworkPolicies (default-deny + allow rules)
uds-package.yaml       # UDS Package CRD (Istio VirtualService, network allows)
zarf.yaml              # Zarf package manifest
uds-bundle.yaml        # UDS Bundle (k3d + Zarf init + UDS Core + app)
Dockerfile             # Multi-stage build
```

---

## UI Features

### BJJ Theme

The UI uses a Brazilian Jiu-Jitsu belt color palette:

| Variable | Value | Used for |
|----------|-------|----------|
| `--belt-white` | `#f5f5f5` | White team pieces, light mode base |
| `--belt-blue` | `#0055d4` | Valid move indicators, primary action color |
| `--belt-purple` | `#6a0dad` | Dark mode primary button |
| `--belt-brown` | `#5d4037` | Board wood texture |
| `--belt-black` | `#121212` | Dark mode base |

Light and dark modes are toggled via the header button and stored on `<html data-theme="dark">`. All colors use CSS custom properties — no hardcoded values.

The game board uses a wood-grain texture (`repeating-linear-gradient`) and renders as a landscape SVG (10 columns wide × 4 rows tall). White starts on the left (rows 1–5), Black on the right (rows 6–10). The dashed centre line runs vertically.

### Voice Control

The app supports Web Speech API voice commands via `useVoiceControl.js`. Toggle the microphone with the **Mic On/Off** button in the header (only shown in supported browsers).

**Move:** `[piece name] to [column][row]`
```
"sleeve to b4"      — moves your Sleeve to column B, row 4
"choke to c6"       — moves your Choke to column C, row 6
```

**Push:** `[piece name] push [direction]`
```
"lapel push down"   — pushes with Lapel toward row 10
"belt push left"    — pushes with Belt toward column A
```

**Skip:** `"skip"` or `"skip moves"` — end the move phase and go straight to pushing.

Only square pieces (Sleeve, Lapel, Belt) can push. Commands are validated against the current player's pieces and game phase before execution.

### Board Coordinate System

Columns A–D run top→bottom (4 rows). Rows 1–10 run left→right (10 columns).

```
   1   2   3   4   5 | 6   7   8   9  10
A  .   .   .   W   . | B   .   .   .   .
B  .   .   W   W   . | B   B   .   .   .
C  .   .   .   W   . | B   .   .   .   .
D  .   .   .   W   . | B   .   .   .   .
                  ↑ centre line (dashed)
```

Kill zones are the leftmost (row 1) and rightmost (row 10) columns, plus the irregular corner cells A2, D2, D3, A8, A9, D9.

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
| `GET` | `/api/game/{id}/valid-moves/{y}/{x}` | Valid move destinations for a piece |
| `GET` | `/api/game/{id}/valid-pushes/{y}/{x}` | Valid push directions for a square piece |
| `POST` | `/api/game/{id}/move` | Make a slide move |
| `POST` | `/api/game/{id}/push` | Make a push |
| `POST` | `/api/game/{id}/skip-moves` | Skip the move phase and go to push |
| `POST` | `/api/game/{id}/ask` | Submit a RAG referee question (answer via WebSocket) |
| `POST` | `/api/game/{id}/save` | Persist game to disk |
| `GET` | `/api/saves` | List saved games |
| `POST` | `/api/game/{id}/load` | Restore game from disk |
| `WS` | `/ws/{id}` | Real-time updates: state, AI moves, RAG answers, errors |

### WebSocket Events (server → client)

| Event | Payload | Description |
|-------|---------|-------------|
| `state_update` | `{ state }` | Full game state after any change |
| `ai_action` | `{ action }` | AI is about to make this move (for highlighting) |
| `ai_done` | — | AI turn complete |
| `rag_answer` | `{ answer }` | RAG referee response to a question |
| `error` | `{ message }` | Server-side error notification |

### Game State Shape

```json
{
  "sessionId": "string",
  "board": [
    [{ "y": 0, "x": 0, "killZone": true, "piece": null, "isAnchor": false }, ...]
  ],
  "currentPlayer": "white" | "black",
  "movesMade": 0,
  "pushCompleted": false,
  "canMove": true,
  "canPush": false,
  "gameOver": false,
  "winner": null | "white" | "black",
  "piecesPushedOff": { "white": { "squares": 0, "rounds": 0 }, "black": { "squares": 0, "rounds": 0 } },
  "mode": "pvp" | "pvai",
  "aiTeam": null | "black",
  "isAiTurn": false
}
```

Piece shape: `{ "team": "white" | "black", "shape": "square" | "round", "name": "sleeve" | "lapel" | "belt" | "choke" | "lock" }`.

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
- **Rewards:** Win +1.0, Loss -1.0, push opponent toward kill zone +0.05
- **Episode limit:** 300 steps
- **Hyperparameters:** n_steps=4096, batch_size=128, gamma=0.995, ent_coef=0.02

---

## Testing

```bash
# Python — all 122 tests
uv run pytest tests/

# Specific suites
uv run pytest tests/test_engine.py      # engine: board, movement, push, win conditions
uv run pytest tests/test_server.py      # FastAPI routes + WebSocket (no 403 bug)
uv run pytest tests/test_integration.py # end-to-end game flow
uv run pytest tests/test_rl_env.py      # RL environment tests
uv run pytest tests/test_storage.py     # save/load round-trips

# Frontend — 61 tests (Vitest + jsdom)
cd frontend && npm test
```

Frontend test suites:
- `Board.test.jsx` — SVG rendering, click handling, piece labels, push arrows
- `useGame.test.js` — game state hook, WebSocket events
- `useVoiceControl.test.js` — voice command parsing (move, push, skip, error cases)
- `api.test.js` — REST API wrapper

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

This bundles the container images (`push-fight-app:latest`, `chromadb/chroma:latest`, `ollama/ollama:latest`) and the manifests into a Zarf package tarball.

### 3. Deploy via UDS Bundle

```bash
uds deploy uds-bundle.yaml
```

The bundle deploys in order:
1. **uds-k3d** — local k3d cluster
2. **init** — Zarf init package (container registry, etc.)
3. **core** — UDS Core (Istio, Pepr, Keycloak, Prometheus, Grafana, …)
4. **push-fight-app** — the Push Fight Zarf package

After deploy, Zarf automatically pulls `llama3` and `nomic-embed-text` into the Ollama pod and waits for all deployments to become available.

### Kubernetes Resources

| Resource | Description |
|----------|-------------|
| `Namespace: push-fight` | Istio injection enabled |
| `Deployment: push-fight-app` | FastAPI + React; liveness/readiness on `GET /health` |
| `Deployment: chromadb` | ChromaDB vector store for RAG |
| `Deployment: ollama` | Ollama LLM inference (llama3 + nomic-embed-text) |
| `Service: push-fight-app` | ClusterIP on port 8000 |
| `UDSPackage: push-fight` | Processed by Pepr → Istio VirtualService + AuthorizationPolicies |
| NetworkPolicies | Default-deny-all + targeted allow rules |

### Environment Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama service URL |
| `CHROMA_HOST` | `chromadb` | ChromaDB service hostname |
| `CHROMA_PORT` | `8000` | ChromaDB service port |

### Accessing the App

After a successful deploy the app is available at:

```
https://push-fight.<uds-domain>
```

The UDS Core tenant Istio gateway routes traffic to `push-fight-app:8000`. WebSocket connections to `/ws/{id}` are handled automatically by Istio (HTTP/1.1 Upgrade).

> **Default UDS dev domain:** `push-fight.uds.dev`

### Persistence

Game saves are stored in `/app/saves` inside the pod, backed by an `emptyDir` volume (lost on pod restart). To persist saves across restarts, replace the `emptyDir` with a PVC in `deployment.yaml`:

```yaml
volumes:
- name: saves
  persistentVolumeClaim:
    claimName: push-fight-saves
```

### Health Probes

| Probe | Endpoint | Initial delay | Period |
|-------|----------|--------------|--------|
| Liveness | `GET /health` | 60 s | 30 s |
| Readiness | `GET /health` | 15 s | 10 s |

---

## Key Design Decisions

- **Piece naming**: BJJ grip/submission names (sleeve, lapel, belt for squares; choke, lock for rounds) are stored in the engine (`pieces.py`) and serialized to the frontend via `state_serializer.py`. Voice control and board labels both use the same names.
- **Board orientation**: The SVG board renders landscape (rows left→right, columns top→bottom) for a more natural widescreen layout. The coordinate transposition is entirely in the frontend — the engine coordinate system (y=row, x=col) is unchanged.
- **WebSocket lifecycle**: `websocket.accept()` must be called before `websocket.close()` in Starlette. Calling close first sends an HTTP 403 response instead of a WS close frame.
- **Voice control field names**: The serialized game state uses camelCase (`currentPlayer`, `canMove`, etc.) — the JS frontend must use camelCase when reading state fields, not Python snake_case.
- **RL generalization**: The RL env uses `is_mine` (relative to current player) rather than absolute team encoding so the single policy generalizes across both sides.
- **Push validation**: `_is_valid_push()` checks legality without mutating game state; `perform_push()` executes once confirmed. The valid-moves method returns a Python `set` — use `next(iter(valid))` not `valid[0]`.
- **Container security**: Runs as non-root UID 1001. `.dockerignore` excludes `.venv/`, `frontend/node_modules/`, `chroma_db/`, and `saves/` to keep the image lean.

---

*Powered by Unicorn Delivery Service*
