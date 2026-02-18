"""
Push Fight — FastAPI web server.

Run with:
    uv run uvicorn app.server.main:app --reload --port 8000

Endpoints
---------
REST
    GET  /health
    POST /api/game                          create new game
    GET  /api/game/{id}                     get current state
    POST /api/game/{id}/move                perform a move
    POST /api/game/{id}/push                perform a push
    POST /api/game/{id}/skip-moves          skip remaining moves (go to push phase)
    GET  /api/game/{id}/valid-moves/{y}/{x} valid move destinations for a piece
    GET  /api/game/{id}/valid-pushes/{y}/{x}valid push directions for a piece
    POST /api/game/{id}/save                save game to disk
    GET  /api/saves                         list saved games
    POST /api/game/{id}/load/{filename}     restore a save into this session
    POST /api/game/{id}/ask                 ask the RAG referee (answer via WS)

WebSocket
    WS   /ws/{id}

    Server → client events (JSON):
        { "event": "state_update", "state": <GameStateResponse> }
        { "event": "ai_action",   "action": <action dict> }
        { "event": "ai_done" }
        { "event": "rag_answer",  "answer": <str> }
        { "event": "error",       "message": <str> }
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.server.models import (
    AskRequest,
    CreateGameRequest,
    MoveRequest,
    PushRequest,
)
from app.server.session import SessionManager
from app.server.state_serializer import serialize_state

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

sessions = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up the RAG engine in the background so it's ready before the first
    # question arrives.  AIInterface is a singleton — the same instance is
    # returned by every subsequent AIInterface() call.
    from app.rag.ai_interface import AIInterface
    AIInterface()
    yield


app = FastAPI(title="Push Fight API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Allow the Vite dev server origin during development.
    # For UDS/Production, restrict this regex to your specific domain (e.g. "https://.*\.uds\.dev")
    # This is now handled by the Vite proxy for local development.
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _broadcast(session_id: str, payload: dict) -> None:
    """Send a JSON message to every WebSocket connected to this session."""
    session = sessions.get(session_id)
    if session is None:
        return
    dead: list = []
    for ws in session.websockets:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        session.websockets.remove(ws)


def _get_session_or_404(session_id: str):
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ---------------------------------------------------------------------------
# AI turn execution (background task)
# ---------------------------------------------------------------------------

async def _run_ai_turn(session_id: str) -> None:
    """
    Execute the AI player's turn step-by-step, broadcasting each action and
    the resulting state over WebSocket so the frontend can animate moves.
    """
    session = sessions.get(session_id)
    if session is None or session.agent is None:
        return

    game = session.game
    agent = session.agent

    await asyncio.sleep(0.4)  # small pause so the client can settle

    max_actions = 5  # safety cap (2 moves + 1 push + buffer)
    for _ in range(max_actions):
        if game.game_over or game.current_player != session.ai_team:
            break

        # Get next action from the RL agent
        try:
            action = agent.get_action(game)
        except Exception as e:
            await _broadcast(session_id, {"event": "error", "message": str(e)})
            break

        if action is None:
            break

        # Announce the action before executing it (lets the UI highlight it)
        await _broadcast(session_id, {"event": "ai_action", "action": action})
        await asyncio.sleep(0.5)

        if action["type"] == "move":
            success, _msg = game.perform_move(action["from"], action["to"])
            if success:
                await _broadcast(
                    session_id,
                    {"event": "state_update", "state": serialize_state(session)},
                )
                await asyncio.sleep(0.4)

        elif action["type"] == "push":
            py, px = action["piece"]
            direction = tuple(action["direction"])
            success = game.perform_push(py, px, direction)
            if success and not game.game_over:
                game.switch_turn()
            await _broadcast(
                session_id,
                {"event": "state_update", "state": serialize_state(session)},
            )
            break  # push ends the AI's turn

    await _broadcast(session_id, {"event": "ai_done"})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


# --- Game lifecycle ---------------------------------------------------------

@app.post("/api/game")
def create_game(body: CreateGameRequest):
    session = sessions.create(mode=body.mode, difficulty=body.difficulty)
    return {"sessionId": session.session_id, "state": serialize_state(session)}


@app.get("/api/game/{session_id}")
def get_game(session_id: str):
    session = _get_session_or_404(session_id)
    return {"state": serialize_state(session)}


# --- Actions ----------------------------------------------------------------

@app.post("/api/game/{session_id}/move")
async def make_move(session_id: str, body: MoveRequest):
    session = _get_session_or_404(session_id)
    game = session.game

    if game.game_over:
        raise HTTPException(status_code=400, detail="Game is already over")

    success, message = game.perform_move(
        tuple(body.from_pos), tuple(body.to_pos)  # type: ignore[arg-type]
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)

    state = serialize_state(session)
    await _broadcast(session_id, {"event": "state_update", "state": state})
    return {"success": True, "message": message, "state": state}


@app.post("/api/game/{session_id}/push")
async def make_push(session_id: str, body: PushRequest):
    session = _get_session_or_404(session_id)
    game = session.game

    if game.game_over:
        raise HTTPException(status_code=400, detail="Game is already over")

    py, px = body.piece
    direction = tuple(body.direction)
    success = game.perform_push(py, px, direction)  # type: ignore[arg-type]

    if not success:
        raise HTTPException(status_code=400, detail="Invalid push")

    # Auto-switch turns (unless game just ended)
    if not game.game_over:
        game.switch_turn()

    state = serialize_state(session)
    await _broadcast(session_id, {"event": "state_update", "state": state})

    # Kick off AI turn in the background if it's now the AI's turn
    if state["isAiTurn"]:
        asyncio.create_task(_run_ai_turn(session_id))

    return {"success": True, "message": "Push executed", "state": state}


@app.post("/api/game/{session_id}/skip-moves")
async def skip_moves(session_id: str):
    """
    Transition from the move phase to the push phase without moving.
    This is a no-op if the player is already in the push phase.
    """
    session = _get_session_or_404(session_id)
    game = session.game

    if game.game_over:
        raise HTTPException(status_code=400, detail="Game is already over")
    if game.push_completed:
        raise HTTPException(status_code=400, detail="Push already completed this turn")

    # Force the move phase to end by setting moves_made to 2
    game.moves_made = 2

    state = serialize_state(session)
    await _broadcast(session_id, {"event": "state_update", "state": state})
    return {"success": True, "state": state}


# --- Valid-action queries ---------------------------------------------------

@app.get("/api/game/{session_id}/valid-moves/{y}/{x}")
def valid_moves(session_id: str, y: int, x: int):
    session = _get_session_or_404(session_id)
    game = session.game

    piece = game.board.get_piece(y, x)
    if not piece or piece == "OUT_OF_BOUNDS":
        raise HTTPException(status_code=400, detail="No piece at that position")
    if piece.team != game.current_player:
        raise HTTPException(status_code=400, detail="Not your piece")
    if not game.can_move():
        return {"moves": []}

    destinations = game.board.get_valid_moves(y, x)
    return {"moves": [list(d) for d in destinations]}


@app.get("/api/game/{session_id}/valid-pushes/{y}/{x}")
def valid_pushes(session_id: str, y: int, x: int):
    session = _get_session_or_404(session_id)
    game = session.game

    piece = game.board.get_piece(y, x)
    if not piece or piece == "OUT_OF_BOUNDS":
        raise HTTPException(status_code=400, detail="No piece at that position")
    if piece.team != game.current_player:
        raise HTTPException(status_code=400, detail="Not your piece")
    if piece.shape != "square":
        raise HTTPException(status_code=400, detail="Only square pieces can push")

    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    valid: list[list[int]] = []
    for dy, dx in directions:
        _, landing = game.board.get_push_chain(y, x, dy, dx)
        if game.board.is_on_board(*landing):
            valid.append([dy, dx])

    return {"directions": valid}


# --- Save / Load -----------------------------------------------------------

@app.post("/api/game/{session_id}/save")
def save_game(session_id: str, filename: str = "game"):
    session = _get_session_or_404(session_id)
    os.makedirs("saves", exist_ok=True)
    filepath = os.path.join("saves", f"{filename}.json")
    session.game.save_to_file(filepath)
    return {"saved": filepath}


@app.get("/api/saves")
def list_saves():
    os.makedirs("saves", exist_ok=True)
    files = [
        f[:-5] for f in os.listdir("saves") if f.endswith(".json")
    ]
    return {"saves": sorted(files)}


@app.post("/api/game/{session_id}/load/{filename}")
async def load_save(session_id: str, filename: str):
    session = _get_session_or_404(session_id)
    filepath = os.path.join("saves", f"{filename}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Save file not found")

    from app.engine.game_state import GameState

    session.game = GameState.load_from_file(filepath)
    state = serialize_state(session)
    await _broadcast(session_id, {"event": "state_update", "state": state})
    return {"success": True, "state": state}


# --- RAG Referee -----------------------------------------------------------

@app.post("/api/game/{session_id}/ask")
async def ask_referee(session_id: str, body: AskRequest):
    """
    Submit a question to the RAG referee.  The answer is delivered
    asynchronously over the session's WebSocket connection as a
    `rag_answer` event rather than in the HTTP response body.
    """
    session = _get_session_or_404(session_id)

    # Capture the running loop now (we're on it); the callback runs in a
    # background thread where asyncio.get_event_loop() raises RuntimeError.
    loop = asyncio.get_running_loop()

    def _callback(answer: str) -> None:
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(
                _broadcast(session_id, {"event": "rag_answer", "answer": answer})
            )
        )

    from app.rag.ai_interface import AIInterface
    ai = AIInterface()
    ai.ask_question(session.game, body.question, _callback)

    return {"status": "question submitted"}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session = sessions.get(session_id)
    if session is None:
        await websocket.close(code=4004)
        return
    session.websockets.append(websocket)

    # Send the current state immediately on connect
    await websocket.send_json(
        {"event": "state_update", "state": serialize_state(session)}
    )

    try:
        while True:
            # Keep the connection alive; the server is the one sending events.
            # If the client sends anything we just ignore it for now.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in session.websockets:
            session.websockets.remove(websocket)


# ---------------------------------------------------------------------------
# Static files — mounted LAST so API routes take priority
# ---------------------------------------------------------------------------

if os.path.isdir(_STATIC_DIR):
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
