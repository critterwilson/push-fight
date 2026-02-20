# Server — FastAPI Web Server

Runs on port 8000. Serves the React app as static files and exposes a REST + WebSocket API for all game actions.

The server follows a **3-layer architecture**: Routes -> Handlers -> Services. Dependencies are wired via constructor injection in `main.py` (the composition root).

## Directory Structure

```
server/
  main.py                  # Composition root — creates app, wires dependencies, includes routers
  session.py               # GameSession dataclass + SessionManager (in-memory session store)
  models.py                # Pydantic request/response models
  state_serializer.py      # Converts GameSession -> camelCase JSON for the frontend

  routes/                  # Thin APIRouter definitions (no business logic)
    game_routes.py         # POST /api/game, GET /api/game/{id}, POST move/push/skip
    setup_routes.py        # POST place, DELETE remove, POST confirm
    query_routes.py        # GET valid-moves, GET valid-pushes
    save_routes.py         # POST save, GET /api/saves, POST load
    rag_routes.py          # POST ask
    websocket_routes.py    # WS /ws/{id}
    health_routes.py       # GET /health

  handlers/                # HTTP translation layer (catches errors, serializes state)
    game_handler.py        # Create, get, move, push, skip
    setup_handler.py       # Place, remove, confirm
    query_handler.py       # Valid moves and pushes
    save_handler.py        # Save, list, load
    rag_handler.py         # Ask referee
    websocket_handler.py   # WebSocket lifecycle (accept, initial state, cleanup)

  services/                # Pure business logic (no HTTP dependencies)
    game_service.py        # Move, push, skip, session lookup
    setup_service.py       # Place, remove, confirm, auto-place
    ai_service.py          # AI turn execution + random fallback
    broadcast_service.py   # WebSocket broadcast + connection pruning
    save_service.py        # Save/load/list (delegates to app.storage)
    rag_service.py         # RAG referee question submission
```

## Layer Responsibilities

| Concern | Routes | Handlers | Services |
|---------|--------|----------|----------|
| Define API endpoints | Yes | - | - |
| Parse request bodies / path params | Yes (FastAPI does it) | Receives parsed values | - |
| Raise HTTPException | - | Yes | No (raises ValueError) |
| Call serialize_state() | - | Yes | - |
| Coordinate multiple services | - | Yes | - |
| Kick off AI turn (asyncio.create_task) | - | Yes | - |
| Game engine calls (perform_move, etc.) | - | - | Yes |
| WebSocket send_json | - | - | Yes (broadcast svc) |
| Disk I/O for saves | - | - | Yes (save svc) |

---

## Running

```bash
uv run uvicorn app.server.main:app --reload --port 8000
```

The Vite dev server proxies `/api` and `/ws` to `http://localhost:8000`. In production, the React build (`frontend/dist/`) is served directly by FastAPI via `StaticFiles`.

---

## REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness/readiness probe |
| `POST` | `/api/game` | Create a new game (`mode`, `difficulty`, `player_color`) |
| `GET` | `/api/game/{id}` | Get full game state |
| `POST` | `/api/game/{id}/setup/place` | Place a piece during setup phase |
| `DELETE` | `/api/game/{id}/setup/{y}/{x}` | Remove a piece during setup phase |
| `POST` | `/api/game/{id}/setup/confirm` | Confirm placement; auto-places AI team in PvAI |
| `POST` | `/api/game/{id}/move` | Slide a piece (`from_pos`, `to_pos`) |
| `POST` | `/api/game/{id}/push` | Execute a push (`piece`, `direction`) |
| `POST` | `/api/game/{id}/skip-moves` | End move phase and go straight to push |
| `GET` | `/api/game/{id}/valid-moves/{y}/{x}` | BFS destinations for a piece |
| `GET` | `/api/game/{id}/valid-pushes/{y}/{x}` | Valid push directions for a square piece |
| `POST` | `/api/game/{id}/save` | Persist game to `saves/<filename>.json` |
| `GET` | `/api/saves` | List saved games |
| `POST` | `/api/game/{id}/load/{filename}` | Restore a save into this session |
| `POST` | `/api/game/{id}/ask` | Submit a RAG referee question (answer delivered via WebSocket) |

---

## WebSocket

**Endpoint:** `WS /ws/{session_id}`

Connects immediately on page load. The server broadcasts events; the client only keeps the connection alive.

### Server -> client events

| Event | Payload | When |
|-------|---------|------|
| `state_update` | `{ state }` | After any game action |
| `ai_action` | `{ action }` | Just before the AI executes a move/push (for UI animation) |
| `ai_done` | -- | AI turn complete |
| `rag_answer` | `{ answer }` | RAG referee response |
| `error` | `{ message }` | Server-side error |

> **Bug note:** `websocket.accept()` must be called before `websocket.close()` in Starlette — calling close first sends an HTTP 403 instead of a WS close frame.

---

## Session Management

`SessionManager` keeps an in-memory dict of `GameSession` objects keyed by UUID. Each session holds:

- `game` — the `GameState` instance
- `mode` — `"pvp"` or `"pvai"`
- `ai_team` — `"white"` or `"black"` (or `None` in PvP)
- `agent` — loaded `Agent` instance (or `None` if no model found)
- `websockets` — list of active WebSocket connections for broadcasting

Multiple browser tabs can connect to the same session and all receive live updates.

---

## AI Turn Orchestration

When it's the AI's turn, `AIService.run_ai_turn()` is run as an `asyncio` background task. It:

1. Calls `agent.get_action(game)` for each step (or falls back to a random valid action if no model is loaded)
2. Broadcasts `ai_action` before executing, with a short delay so the UI can highlight the move
3. Broadcasts `state_update` after each action
4. Broadcasts `ai_done` when the turn ends

---

## State Serializer

`state_serializer.py` converts the internal `GameState` (snake_case, Python objects) into the camelCase JSON shape the frontend expects:

```json
{
  "sessionId": "...",
  "board": [[{ "y": 0, "x": 0, "killZone": true, "piece": null, "isAnchor": false }, ...]],
  "currentPlayer": "white",
  "movesMade": 0,
  "pushCompleted": false,
  "canMove": true,
  "canPush": false,
  "gameOver": false,
  "winner": null,
  "piecesPushedOff": { "white": { "squares": 0, "rounds": 0 }, "black": { "squares": 0, "rounds": 0 } },
  "mode": "pvai",
  "aiTeam": "black",
  "isAiTurn": false
}
```

Piece shape: `{ "team": "white"|"black", "shape": "square"|"round", "name": "sleeve"|"lapel"|... }`.

> The `name` field must be present in the piece dict — voice control on the frontend depends on it.
