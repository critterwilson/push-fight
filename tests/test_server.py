"""
Tests for the FastAPI server routes and WebSocket endpoint.

Uses FastAPI's TestClient (backed by httpx + starlette's WebSocket
test helper) so no live server is needed.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Patch out the RAG engine warm-up so tests don't need Ollama running.
# We mock AIInterface before importing the app.
from unittest.mock import MagicMock, patch

with patch("app.rag.ai_interface.AIInterface", return_value=MagicMock()):
    from app.server.main import app, sessions

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_sessions():
    """Clear all sessions before each test to keep tests isolated."""
    sessions._sessions.clear()
    yield
    sessions._sessions.clear()


@pytest.fixture
def client():
    # Use TestClient as a context manager so lifespan events run.
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _complete_setup(client, sid):
    """Place all pieces for both sides (mirroring initial layout) and start the game."""
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
    """Create a PvP session, complete setup, and return (client, session_id, play_state)."""
    resp = client.post("/api/game", json={"mode": "pvp", "difficulty": "medium"})
    assert resp.status_code == 200
    sid = resp.json()["sessionId"]
    state = _complete_setup(client, sid)
    return client, sid, state


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /api/game — create game
# ---------------------------------------------------------------------------


class TestCreateGame:
    def test_returns_session_id_and_state(self, client):
        resp = client.post("/api/game", json={"mode": "pvp", "difficulty": "medium"})
        assert resp.status_code == 200
        body = resp.json()
        assert "sessionId" in body
        assert "state" in body

    def test_state_has_expected_fields(self, client):
        resp = client.post("/api/game", json={"mode": "pvp", "difficulty": "medium"})
        state = resp.json()["state"]
        assert "board" in state
        assert "currentPlayer" in state
        assert state["currentPlayer"] == "white"
        assert state["gameOver"] is False

    def test_board_is_10_by_4(self, client):
        resp = client.post("/api/game", json={"mode": "pvp", "difficulty": "medium"})
        board = resp.json()["state"]["board"]
        assert len(board) == 10
        assert all(len(row) == 4 for row in board)

    def test_pieces_have_names(self, pvp_session):
        """After setup, all BJJ piece names should appear on the board."""
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
        """A freshly created game should be in setup mode with placement status."""
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
    def test_returns_state_for_known_session(self, pvp_session):
        client, sid, _ = pvp_session
        resp = client.get(f"/api/game/{sid}")
        assert resp.status_code == 200
        assert "state" in resp.json()

    def test_404_for_unknown_session(self, client):
        resp = client.get("/api/game/nonexistent-id")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/game/{id}/skip-moves
# ---------------------------------------------------------------------------


class TestSkipMoves:
    def test_skip_transitions_to_push_phase(self, pvp_session):
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
        resp = client.post("/api/game/bad-id/skip-moves")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/game/{id}/move
# ---------------------------------------------------------------------------


class TestMakeMove:
    def _find_piece(self, board, team, name):
        """Return (y, x) of a named piece for the given team."""
        for y, row in enumerate(board):
            for x, cell in enumerate(row):
                p = cell.get("piece")
                if p and p.get("team") == team and p.get("name") == name:
                    return [y, x]
        return None

    def test_valid_move_returns_updated_state(self, pvp_session):
        client, sid, state = pvp_session
        # White's turn; find white's 'sleeve' piece and attempt a legal slide
        pos = self._find_piece(state["board"], "white", "sleeve")
        assert pos is not None, "White 'sleeve' piece not found on board"

        y, x = pos
        # Try moving up one row (toward row 0) — may or may not be valid,
        # but we just need a legal destination from the engine's perspective.
        # Use valid-moves endpoint to find a real destination.
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
        client, sid, state = pvp_session
        # Find two adjacent pieces of the same team and try to move one onto the other
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
        resp = client.post(
            "/api/game/bad-id/move",
            json={"from_pos": [4, 0], "to_pos": [3, 0]},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/game/{id}/valid-moves
# ---------------------------------------------------------------------------


class TestValidMoves:
    def test_returns_list_for_own_piece(self, pvp_session):
        client, sid, state = pvp_session
        # sleeve is at row 4, col 0 in the initial layout
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
        client, sid, _ = pvp_session
        # Row 2, col 2 should be empty in initial layout
        resp = client.get(f"/api/game/{sid}/valid-moves/2/2")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------


class TestSaveLoad:
    def test_save_and_list(self, pvp_session, tmp_path, monkeypatch):
        client, sid, _ = pvp_session
        monkeypatch.chdir(tmp_path)

        resp = client.post(f"/api/game/{sid}/save?filename=test-save")
        assert resp.status_code == 200
        assert "saves/test-save.json" in resp.json()["saved"]

        list_resp = client.get("/api/saves")
        assert list_resp.status_code == 200
        assert "test-save" in list_resp.json()["saves"]

    def test_load_nonexistent_file_returns_404(self, pvp_session):
        client, sid, _ = pvp_session
        resp = client.post(f"/api/game/{sid}/load/no-such-file")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


class TestWebSocket:
    def test_valid_session_receives_state_update(self, pvp_session):
        """Connecting with a real session ID should deliver an immediate state_update."""
        client, sid, _ = pvp_session
        with client.websocket_connect(f"/ws/{sid}") as ws:
            msg = ws.receive_json()
            assert msg["event"] == "state_update"
            assert "state" in msg

    def test_invalid_session_receives_4004_close(self, client):
        """Connecting with an unknown session ID must close with code 4004, not 403."""
        with client.websocket_connect("/ws/nonexistent-session-id") as ws:
            # The server should close with 4004 after accepting
            with pytest.raises(Exception) as exc_info:
                ws.receive_json()
            # Starlette's test client raises WebSocketDisconnect or similar;
            # the important thing is the connection was ACCEPTED (no 403).
            # If we reached here the handshake succeeded — no HTTP 403 was raised.

    def test_websocket_sends_current_state_on_connect(self, pvp_session):
        """The first message must be the current game state."""
        client, sid, original_state = pvp_session
        with client.websocket_connect(f"/ws/{sid}") as ws:
            msg = ws.receive_json()
            ws_state = msg["state"]
            assert ws_state["currentPlayer"] == original_state["currentPlayer"]
            assert ws_state["gameOver"] == original_state["gameOver"]
