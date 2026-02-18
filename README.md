# Push Fight: BJJ Edition

A digital adaptation of [Push Fight](https://pushfightgame.com/) — a 2-player abstract strategy game — themed around Brazilian Jiu-Jitsu.

---

## Why I Built This

Chess gets recommended constantly as a thinking game for BJJ players. The problem is that chess rewards material accumulation and positional dominance over time — it doesn't map well to the way grappling actually works.

In BJJ, position is temporary. Control is always contested. The moment you commit to a move, your opponent is already adjusting. You're not trying to collect pieces; you're trying to force someone off a stable position until they fall off the edge. The game ends when someone gets pushed out, not captured.

Push Fight captures that feeling better than chess does. There's no material economy. Every piece matters. Position is everything, and the board is small enough that a single push can end the game. I built this as an experiment to see if a board game could actually replicate the strategic logic of BJJ — the pressure game, the scrambles, the importance of the anchor.

The BJJ piece names (sleeve, lapel, belt, neck, joint) are a nod to the grips and positions that give control in grappling. Square pieces are the active grips that can do work; round pieces are the submissions — lose one and the match is over instantly.

---

## The Game

Push Fight is played on an irregular 10×4 board with kill zones at each end. Each player has **5 pieces**: 3 squares (pushers) and 2 rounds (blockers).

### Turn Structure

1. **Move phase** (optional): slide 0–2 of your pieces any number of squares orthogonally
2. **Push phase** (mandatory): push with one square piece — all pieces in the chain shift one square in the push direction

After pushing, an **anchor** is placed on the pushing piece, preventing the opponent from moving or pushing it next turn.

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

Columns A–D run top→bottom (4 rows). Rows 1–10 run left→right (10 columns). Kill zones are the leftmost and rightmost columns, plus several irregular corner cells.

```
   1   2   3   4   5 | 6   7   8   9  10
A  .   .   .   W   . | B   .   .   .   .
B  .   .   W   W   . | B   B   .   .   .
C  .   .   .   W   . | B   .   .   .   .
D  .   .   .   W   . | B   .   .   .   .
                  ↑ centre line (dashed)
```

White starts on the left (rows 1–5), Black on the right (rows 6–10).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser                                                     │
│  React + Vite (SVG board, voice control, RAG chat panel)    │
└───────────────────┬─────────────────────────────────────────┘
                    │ REST + WebSocket (/ws/{id})
┌───────────────────▼─────────────────────────────────────────┐
│  FastAPI  —  port 8000                                       │
│  Session management · AI turn orchestration · Static files  │
└──────┬─────────────────────┬────────────────────────────────┘
       │                     │
┌──────▼──────┐    ┌─────────▼──────────┐    ┌───────────────┐
│  engine/    │    │  rl/  (AI)          │    │  rag/         │
│  Core game  │    │  MaskablePPO        │    │  LangChain +  │
│  logic      │    │  self-play agent    │    │  ChromaDB +   │
└─────────────┘    └────────────────────┘    │  Ollama       │
                                             └───────────────┘
```

The system has four backend modules, each documented separately:

| Module | What it does | README |
|--------|-------------|--------|
| `app/engine/` | Board, pieces, game rules, win conditions | [engine/README.md](app/engine/README.md) |
| `app/server/` | FastAPI REST + WebSocket API, session management | [server/README.md](app/server/README.md) |
| `app/rl/` | MaskablePPO training, self-play, difficulty presets | [rl/README.md](app/rl/README.md) |
| `app/rag/` | RAG referee — LangChain, ChromaDB, Ollama | [rag/README.md](app/rag/README.md) |
| `app/storage/` | Save / load game state to JSON | [storage/README.md](app/storage/README.md) |
| `app/pygame_ui/` | Legacy PyGame desktop UI (local only) | [pygame_ui/README.md](app/pygame_ui/README.md) |

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

## Local Development

### Prerequisites

- Python 3.13+ with [uv](https://github.com/astral-sh/uv)
- Node 22+ with npm
- [Ollama](https://ollama.com/) with `llama3` and `nomic-embed-text` pulled (for the RAG referee)

### Backend

```bash
uv sync --dev
uv run uvicorn app.server.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

The Vite dev server proxies `/api` and `/ws` to `http://localhost:8000`.

### Tests

```bash
# Python (122 tests)
uv run pytest tests/

# Frontend (61 tests, Vitest + jsdom)
cd frontend && npm test
```

### Legacy PyGame UI

```bash
uv run python -m app.pygame_ui.main
```

---

## UI Features

### Voice Control

Toggle the microphone with the **Mic On/Off** button (supported browsers only). Commands:

```
"sleeve to b4"      — move your Sleeve to column B, row 4
"lapel push down"   — push with Lapel toward row 10
"skip"              — end move phase and go to push
```

### Board Orientation

The SVG board renders landscape (rows left→right, columns top→bottom). The coordinate transposition is entirely in the frontend — the engine coordinate system `(y=row, x=col)` is unchanged.

### BJJ Theme

Colors use a Brazilian Jiu-Jitsu belt palette (`--belt-white`, `--belt-blue`, `--belt-purple`, `--belt-brown`, `--belt-black`). Light and dark mode are toggled via the header button.

---

## UDS Deployment

The app is packaged with [Zarf](https://zarf.dev) and deployed via a [UDS Bundle](https://github.com/defenseunicorns/uds-cli) that includes k3d, Zarf init, UDS Core (Istio + Pepr + Keycloak), and the Push Fight app.

```bash
docker build -t push-fight-app:latest .
zarf package create .
uds deploy uds-bundle.yaml
```

After deploy: `https://push-fight.uds.dev`

Environment variables for services: `OLLAMA_HOST`, `CHROMA_HOST`, `CHROMA_PORT`.

---

*Powered by Unicorn Delivery Service*
