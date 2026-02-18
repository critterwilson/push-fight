# Push Fight — Web Migration Plan

## Overview

Migrate from PyGame to a deployable web application using UDS.

**Stack:**
- **Backend:** FastAPI (Python) + WebSockets — wraps existing game engine with zero rewrites
- **Frontend:** React + Vite — SVG-based board rendering
- **Deployment:** Single container (FastAPI serves the built React app as static files)

**What stays the same:** `app/engine/`, `app/rl/`, `app/rag/`, `app/storage/`, all tests, models, assets.

---

## Phase 1 — FastAPI Game Server

Create `app/server/` with session-based game management and a full API layer.

**Session management**
- Server-side `GameState` objects keyed by session ID
- Supports multiple concurrent games

**REST endpoints**
- `POST /api/game` — create new game (mode: PvP/PvAI, difficulty)
- `GET /api/game/{id}` — get full game state as JSON
- `POST /api/game/{id}/move` — make a move
- `POST /api/game/{id}/push` — make a push
- `POST /api/game/{id}/save` — persist game to disk
- `GET /api/game/{id}/load` — restore game from disk
- `GET /health` — health/readiness probe

**WebSocket**
- `/ws/{id}` — pushes state updates to the client (AI moves, RAG answers, game over)
- `POST /api/game/{id}/ask` — submit a RAG referee question (answer delivered over WS)

**Status:** [x] Complete

Files created:
- `app/server/__init__.py`
- `app/server/session.py` — `GameSession` dataclass + `SessionManager`
- `app/server/models.py` — Pydantic request/response models
- `app/server/state_serializer.py` — game state → frontend JSON
- `app/server/main.py` — FastAPI app (all REST routes + WebSocket)

Run locally with:
```
uv run uvicorn app.server.main:app --reload --port 8000
```

---

## Phase 2 — React Frontend

Create `frontend/` (Vite + React) with full game UI.

**Components**
- `Board` — SVG grid: 10×4 board, kill zones, pieces (color + shape), anchor marker
- `Interaction layer` — click piece → highlight valid moves → click destination → push direction buttons (↑↓←→)
- `StatusBar` — current player, turn phase (move/push), moves remaining, game mode
- `GameControls` — New Game, mode/difficulty selection, Save/Load
- `ChatPanel` — RAG referee chat (mirrors existing PyGame chat overlay)

**Status:** [x] Complete

Files created:
- `frontend/package.json`, `frontend/vite.config.js`, `frontend/index.html`
- `frontend/src/main.jsx` — React entry point
- `frontend/src/App.jsx` — layout, New Game modal, board legend
- `frontend/src/api.js` — all REST calls with error handling
- `frontend/src/useGame.js` — game state hook (REST + WebSocket)
- `frontend/src/Board.jsx` — SVG board, pieces, push-direction arrows
- `frontend/src/StatusBar.jsx` — turn/phase display, pieces lost
- `frontend/src/GameControls.jsx` — skip-moves, direction pad, save/load
- `frontend/src/ChatPanel.jsx` — RAG referee chat
- `frontend/src/index.css` — dark theme, responsive layout

Run dev server:
```
cd frontend && npm run dev      # http://localhost:3000
uv run uvicorn app.server.main:app --reload --port 8000
```

---

## Phase 3 — Integration & Polish

- WebSocket wiring so AI moves animate step-by-step
- RAG answers stream into chat panel in real time
- Error boundaries and WebSocket reconnection logic
- Mobile-friendly responsive layout
- Basic accessibility (keyboard navigation, ARIA labels)
- Comprehesive tests implemented
- Build a tmuxinator file to start the local server and frontend. Don't include this file in git or UDS deployment.

**Status:** [x] Complete

Changes:
- `useGame.js` — WebSocket auto-reconnect (2 s backoff), session-expired detection (code 4004), `pendingAiAction` state for pre-move highlighting, `connectionStatus` state
- `Board.jsx` — ARIA `role="application"` + `aria-label` on SVG; each cell has `role="button"`, `aria-label`, `aria-pressed`, `tabIndex`, keyboard (`Enter`/`Space`) handler; push arrows have `aria-label="Push <dir>"`; AI-pending cells get a pulsing orange glow
- `App.jsx` — `ErrorBoundary` wraps game area; connection status pip in header; `role="alert"` on error toast; `role="dialog"` + `aria-modal` on modal
- `ErrorBoundary.jsx` — class component catches render errors, shows reset button
- `frontend/src/tests/api.test.js` — 12 tests covering all API functions
- `frontend/src/tests/Board.test.jsx` — 11 tests (rendering, clicks, ARIA, arrows)
- `frontend/src/tests/useGame.test.js` — 10 tests (state, WS events, reconnect, actions)
- `.tmuxinator.yml` — local dev session (added to `.gitignore`)
- `.gitignore` — excludes `.tmuxinator.yml`, `frontend/dist/`, `frontend/node_modules/`

Run all 33 frontend tests:
```
cd frontend && npm test
```

Start local dev:
```
tmuxinator start -p .tmuxinator.yml
# or manually:
uv run uvicorn app.server.main:app --reload --port 8000
cd frontend && npm run dev
```

---

## Phase 4 — UDS Deployment

- **Dockerfile** — multi-stage build: stage 1 builds React (`npm run build`), stage 2 is Python slim with static files copied in; FastAPI serves them via `StaticFiles`
- **`deployment.yaml`** — update push-fight service to serve both API and UI on port 8000; remove need for separate nginx container
- **`zarf.yaml` / `uds-bundle.yaml`** — update image refs; Ollama + ChromaDB services remain for RAG
- **Health/readiness probes** — wired to `GET /health`

**Status:** [x] Complete

Files created / modified:
- `Dockerfile` — two-stage build (Node 22 → React dist; Python 3.13-slim → uvicorn). `COPY . .` replaced with selective copies so `.dockerignore` keeps the image lean
- `.dockerignore` — excludes `.venv/`, `frontend/node_modules/`, `frontend/dist/`, `chroma_db/`, `saves/`, docs, OS noise
- `deployment.yaml` — push-fight-app gains `containerPort: 8000`, `livenessProbe` + `readinessProbe` on `GET /health`, `emptyDir` volume for `/app/saves`, and a new `Service` on port 8000. PVC upgrade path noted in comments.
- `uds-package.yaml` (new) — `UDSPackage` CRD processed by Pepr: exposes `push-fight-app` via the tenant gateway on host `push-fight`; network allow rules for ingress from Istio gateway, egress to ChromaDB (8000) and Ollama (11434), and kube-dns
- `zarf.yaml` — `uds-package.yaml` added to the manifests list

Build and deploy:
```bash
# Build the image
docker build -t push-fight-app:latest .

# Create Zarf package
zarf package create .

# Deploy via UDS
uds deploy uds-bundle.yaml
```

The app is served at `https://push-fight.<uds-domain>` through the tenant gateway.
WebSocket connections to `/ws/{id}` are handled automatically by Istio.
