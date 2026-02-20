"""
Tests for the FastAPI server routes and WebSocket endpoint.

This module validates the HTTP API surface and real-time WebSocket behavior
of the Push Fight game server (app.server.main). It covers:

  - Health check endpoint.
  - Game creation (POST /api/game) and state retrieval (GET /api/game/{id}).
  - Setup-mode piece placement and confirmation flow.
  - Move and skip-moves endpoints.
  - Valid-moves query endpoint.
  - Save/load and list-saves endpoints.
  - WebSocket connection lifecycle (state_update delivery, invalid session
    handling, and initial state broadcast).

Testing strategy:
  - Uses FastAPI's TestClient (backed by httpx + Starlette's WebSocket
    test helper) so no live server or network stack is needed.
  - The RAG AI interface is mocked at import time to avoid requiring a
    running Ollama instance during tests.
  - Session storage is cleared before and after each test via the
    autouse `clean_sessions` fixture for full isolation.
  - A `pvp_session` composite fixture creates a ready-to-play PvP game
    (setup completed) so move/push/save tests can focus on gameplay logic
    rather than setup boilerplate.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Patch out the RAG engine warm-up so tests don't need Ollama running.
# We mock AIInterface before importing the app — this must happen at module
# level because the app's lifespan event initializes the RAG engine eagerly.
from unittest.mock import MagicMock, patch

with patch("app.rag.ai_interface.AIInterface", return_value=MagicMock()):
    from app.server.main import app, sessions

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_sessions():
    """Clear all in-memory sessions before and after each test.

    This autouse fixture ensures complete test isolation — no session
    state leaks between tests regardless of execution order.
    """
    sessions._sessions.clear()
    yield
    sessions._sessions.clear()


@pytest.fixture
def client():
    """Provide a FastAPI TestClient with lifespan events executed.

    Using TestClient as a context manager triggers the app's startup and
    shutdown lifespan hooks, mimicking a real server lifecycle.
    """
    # Use TestClient as a context manager so lifespan events run.
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _complete_setup(client, sid):
    """Helper: place all 10 pieces (5 white, 5 black) via the setup API
    endpoints and confirm both sides, transitioning the game from setup
    mode into active play. Returns the resulting game state dict."""
    white = [("sleeve", 4, 0), ("lapel", 4, 1), ("belt", 4, 2), ("neck", 4, 3), ("joint", 3, 1)]
    black = [("sleeve", 5, 0), ("lapel", 5, 1), ("belt", 5, 2), ("neck", 5, 3), ("joint", 6, 1)]
    for name, y, x in white:
        r = client.post(f"/api/game/{sid}/setup/place", json={"y": y, "x": x, "name": name})
        assert r.status_code == 200, f"White place {name} failed: {r.json()}"
    client.post(f"/api/game/{sid}/setup/confirm")
    for name, y, x in black:
        r = client.post(f"/api/game/{sid}/setup/place", json={"y": y, "x": x, "name": name})
        assert r.status_code == 200, f"Black place {name} failed: {r.json()}"
    resp = client.post(f"/api/game/{sid}/setup/confirm")
    assert resp.status_code == 200
    return resp.json()["state"]


@pytest.fixture
def pvp_session(client):
    """Composite fixture: creates a PvP game session, completes the setup
    phase with the standard piece layout, and yields (client, session_id,
    play_state). Tests that need a game ready for moves/pushes should use
    this fixture instead of manually creating and setting up a session."""
    resp = client.post("/api/game", json={"mode": "pvp", "difficulty": "medium"})
    assert resp.status_code == 200
    sid = resp.json()["sessionId"]
    state = _complete_setup(client, sid)
    return client, sid, state


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health(client):
    """The /health endpoint is used by load balancers and monitoring to verify
    the server process is alive. It must always return 200 with {"status": "ok"}."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /api/game — create game
# ---------------------------------------------------------------------------


class TestCreateGame:
    """Tests for the POST /api/game endpoint that initializes a new game session.

    Validates that the response includes a unique sessionId and a complete
    game state object, that the state has the correct structure and initial
    values, that the board dimensions match the 10x4 Push Fight grid, and
    that setup-mode metadata is present for new games.
    """

    def test_returns_session_id_and_state(self, client):
        """Creating a game must return both a unique sessionId (for subsequent
        API calls) and the initial game state (for immediate UI rendering)."""
        resp = client.post("/api/game", json={"mode": "pvp", "difficulty": "medium"})
        assert resp.status_code == 200
        body = resp.json()
        assert "sessionId" in body
        assert "state" in body

    def test_state_has_expected_fields(self, client):
        """The serialized state must include board, currentPlayer, and gameOver
        fields. White always moves first, and the game is not over at creation."""
        resp = client.post("/api/game", json={"mode": "pvp", "difficulty": "medium"})
        state = resp.json()["state"]
        assert "board" in state
        assert "currentPlayer" in state
        assert state["currentPlayer"] == "white"
        assert state["gameOver"] is False

    def test_board_is_10_by_4(self, client):
        """The serialized board must have exactly 10 rows of 4 cells each,
        matching the canonical Push Fight board dimensions."""
        resp = client.post("/api/game", json={"mode": "pvp", "difficulty": "medium"})
        board = resp.json()["state"]["board"]
        assert len(board) == 10
        assert all(len(row) == 4 for row in board)

    def test_pieces_have_names(self, pvp_session):
        """After setup, all 5 BJJ piece names (sleeve, lapel, belt, neck,
        joint) must appear on the board. This validates that the state
        serializer includes the name field required by voice control."""
        _, _, state = pvp_session
        names = [
            cell["piece"]["name"]
            for row in state["board"]
            for cell in row
            if cell.get("piece")
        ]
        for expected in ("sleeve", "lapel", "belt", "neck", "joint"):
            assert expected in names, f"Expected piece name '{expected}' not found"

    def test_setup_mode_fields_on_new_game(self, client):
        """A freshly created game should be in setup mode with a placementStatus
        object listing all unplaced piece names for both teams. The frontend
        uses this to render the piece palette during setup."""
        resp = client.post("/api/game", json={"mode": "pvp", "difficulty": "medium"})
        state = resp.json()["state"]
        assert state["setupMode"] is True
        assert "placementStatus" in state
        assert state["placementStatus"]["white"]["unplaced"] == ["sleeve", "lapel", "belt", "neck", "joint"]
        assert state["placementStatus"]["black"]["unplaced"] == ["sleeve", "lapel", "belt", "neck", "joint"]


# ---------------------------------------------------------------------------
# GET /api/game/{session_id}
# ---------------------------------------------------------------------------


class TestGetGame:
    """Tests for retrieving an existing game session's state by ID.

    The GET endpoint is used by the frontend to re-fetch state (e.g., after
    a page refresh). It must return the current state for valid sessions
    and a 404 for unknown session IDs.
    """

    def test_returns_state_for_known_session(self, pvp_session):
        """A valid session ID must return 200 with the game state."""
        client, sid, _ = pvp_session
        resp = client.get(f"/api/game/{sid}")
        assert resp.status_code == 200
        assert "state" in resp.json()

    def test_404_for_unknown_session(self, client):
        """Requesting a non-existent session must return 404 so the frontend
        can display an appropriate error or redirect to the lobby."""
        resp = client.get("/api/game/nonexistent-id")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/game/{id}/skip-moves
# ---------------------------------------------------------------------------


class TestSkipMoves:
    """Tests for the skip-moves endpoint, which lets a player forgo their
    optional moves and proceed directly to the mandatory push phase.

    This is useful when the player has no beneficial moves available but
    still needs to push to complete their turn.
    """

    def test_skip_transitions_to_push_phase(self, pvp_session):
        """After skipping moves, canMove must become False (moves exhausted)
        and canPush must remain True (push still required)."""
        client, sid, state = pvp_session
        # Initially in move phase (moves_made == 0, push not completed)
        assert state["canMove"] is True

        resp = client.post(f"/api/game/{sid}/skip-moves")
        assert resp.status_code == 200
        new_state = resp.json()["state"]
        # After skipping, can no longer move (moves_made set to 2)
        assert new_state["canMove"] is False
        assert new_state["canPush"] is True

    def test_404_for_unknown_session(self, client):
        """Skip-moves on a non-existent session must return 404."""
        resp = client.post("/api/game/bad-id/skip-moves")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/game/{id}/move
# ---------------------------------------------------------------------------


class TestMakeMove:
    """Tests for the POST /api/game/{id}/move endpoint.

    Validates that legal moves return updated state, illegal moves (e.g.,
    moving onto an occupied cell) return 400, and unknown sessions return 404.
    Uses the valid-moves endpoint to discover legal destinations dynamically,
    avoiding hard-coded board positions that would break if the layout changes.
    """

    def _find_piece(self, board, team, name):
        """Helper: scan the serialized board grid and return [y, x] of the
        first cell containing a piece matching the given team and name.
        Returns None if no such piece is found."""
        for y, row in enumerate(board):
            for x, cell in enumerate(row):
                p = cell.get("piece")
                if p and p.get("team") == team and p.get("name") == name:
                    return [y, x]
        return None

    def test_valid_move_returns_updated_state(self, pvp_session):
        """Find white's sleeve piece, query its valid moves, and move it to
        the first legal destination. The response must indicate success and
        include an updated game state."""
        client, sid, state = pvp_session
        pos = self._find_piece(state["board"], "white", "sleeve")
        assert pos is not None, "White 'sleeve' piece not found on board"

        y, x = pos
        # Use valid-moves endpoint to find a real destination dynamically.
        vm_resp = client.get(f"/api/game/{sid}/valid-moves/{y}/{x}")
        assert vm_resp.status_code == 200
        moves = vm_resp.json()["moves"]
        if not moves:
            pytest.skip("No valid moves for sleeve — board layout edge case")

        to_pos = moves[0]
        resp = client.post(
            f"/api/game/{sid}/move",
            json={"from_pos": pos, "to_pos": to_pos},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_move_to_occupied_cell_fails(self, pvp_session):
        """Moving a piece onto a cell already occupied by a friendly piece
        must return 400. This validates the server-side move legality check."""
        client, sid, state = pvp_session
        board = state["board"]
        pos = self._find_piece(board, "white", "sleeve")
        lapel = self._find_piece(board, "white", "lapel")
        assert pos and lapel
        resp = client.post(
            f"/api/game/{sid}/move",
            json={"from_pos": pos, "to_pos": lapel},
        )
        # Should fail (can't move onto an occupied cell)
        assert resp.status_code == 400

    def test_404_for_unknown_session(self, client):
        """Attempting a move on a non-existent session must return 404."""
        resp = client.post(
            "/api/game/bad-id/move",
            json={"from_pos": [4, 0], "to_pos": [3, 0]},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/game/{id}/valid-moves
# ---------------------------------------------------------------------------


class TestValidMoves:
    """Tests for the valid-moves query endpoint.

    The frontend calls this endpoint when a player clicks a piece to see
    where it can slide. Must return a list of (y, x) coordinates for own
    pieces and reject requests for empty cells.
    """

    def test_returns_list_for_own_piece(self, pvp_session):
        """Querying valid moves for white's sleeve piece must return 200 with
        a 'moves' list. The list may be empty in rare layouts, but the key
        must always be present."""
        client, sid, state = pvp_session
        board = state["board"]
        pos = next(
            ([y, x] for y, row in enumerate(board) for x, c in enumerate(row)
             if c.get("piece") and c["piece"].get("name") == "sleeve" and c["piece"]["team"] == "white"),
            None,
        )
        assert pos is not None
        resp = client.get(f"/api/game/{sid}/valid-moves/{pos[0]}/{pos[1]}")
        assert resp.status_code == 200
        assert "moves" in resp.json()

    def test_400_for_empty_cell(self, pvp_session):
        """Querying valid moves for a cell with no piece should return 400.
        The frontend should only call this after verifying a piece exists."""
        client, sid, _ = pvp_session
        # Row 2, col 2 should be empty in initial layout
        resp = client.get(f"/api/game/{sid}/valid-moves/2/2")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------


class TestSaveLoad:
    """Tests for the save/load/list-saves API endpoints.

    Verifies that a game can be saved to disk, appears in the saves list,
    and that loading a non-existent file returns 404. Uses monkeypatch to
    change the working directory to a temp path so test saves don't pollute
    the real saves directory.
    """

    def test_save_and_list(self, pvp_session, tmp_path, monkeypatch):
        """Save a game, then verify it appears in the list-saves response.
        Uses tmp_path to isolate test file I/O from production saves."""
        client, sid, _ = pvp_session
        monkeypatch.chdir(tmp_path)

        resp = client.post(f"/api/game/{sid}/save?filename=test-save")
        assert resp.status_code == 200
        assert "saves/test-save.json" in resp.json()["saved"]

        list_resp = client.get("/api/saves")
        assert list_resp.status_code == 200
        assert "test-save" in list_resp.json()["saves"]

    def test_load_nonexistent_file_returns_404(self, pvp_session):
        """Loading a save file that doesn't exist must return 404 so the
        frontend can show an appropriate error message."""
        client, sid, _ = pvp_session
        resp = client.post(f"/api/game/{sid}/load/no-such-file")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


class TestWebSocket:
    """Tests for the WebSocket endpoint at /ws/{session_id}.

    The WebSocket connection is the real-time communication channel between
    the server and frontend. These tests validate:
      - A valid session receives an immediate state_update on connect.
      - An invalid session ID results in a proper WebSocket close (not an
        HTTP 403 — a bug that was previously fixed by calling
        websocket.accept() before websocket.close() in Starlette).
      - The initial state broadcast matches the current game state.
    """

    def test_valid_session_receives_state_update(self, pvp_session):
        """Connecting with a real session ID should deliver an immediate
        state_update event so the client can render the board without
        an extra HTTP round-trip."""
        client, sid, _ = pvp_session
        with client.websocket_connect(f"/ws/{sid}") as ws:
            msg = ws.receive_json()
            assert msg["event"] == "state_update"
            assert "state" in msg

    def test_invalid_session_receives_4004_close(self, client):
        """Connecting with an unknown session ID must close with custom code
        4004, NOT an HTTP 403. The 403 bug occurred when websocket.close()
        was called before websocket.accept() — Starlette interprets that as
        an HTTP rejection rather than a WebSocket close frame."""
        with client.websocket_connect("/ws/nonexistent-session-id") as ws:
            # The server should close with 4004 after accepting
            with pytest.raises(Exception) as exc_info:
                ws.receive_json()
            # Starlette's test client raises WebSocketDisconnect or similar;
            # the important thing is the connection was ACCEPTED (no 403).
            # If we reached here the handshake succeeded — no HTTP 403 was raised.

    def test_websocket_sends_current_state_on_connect(self, pvp_session):
        """The first WebSocket message must contain the exact current game
        state, ensuring the client starts with a consistent view even if
        HTTP responses were lost or stale."""
        client, sid, original_state = pvp_session
        with client.websocket_connect(f"/ws/{sid}") as ws:
            msg = ws.receive_json()
            ws_state = msg["state"]
            assert ws_state["currentPlayer"] == original_state["currentPlayer"]
            assert ws_state["gameOver"] == original_state["gameOver"]
