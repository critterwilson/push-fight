# Cleanup & Fix Plan

## 1. Bug Fixes ✅ COMPLETE

### 1.1 `app/rl/play_against_ai.py` - Duplicate code & broken references ✅
- **Problem:** File loads the model twice (once via `PushFightAgent` line 359, again via raw `MaskablePPO.load` line 368). The `ai_turn()` function calls `get_ai_action(env, model, ...)` then immediately overwrites with `agent.get_action(...)` on lines 213-214 and 235-236. Fallback block (lines 255-264) references both `env` and `agent.env`. Game loop (lines 394-395) calls `ai_turn()` with two different signatures.
- **Fix:** Removed the standalone `get_ai_action()` function, the raw `env`/`model` variables, and the duplicate `MaskablePPO.load` call. Uses `PushFightAgent` exclusively throughout. `ai_turn()` accepts `(agent, game_state)` only.

### 1.2 `app/cli.py:394` - Wrong team name ✅
- **Problem:** `game.winner = 'brown'` should be `'black'`.
- **Fix:** Changed `'brown'` to `'black'`.

### 1.3 `app/web/routes.py` - Wrong team name ✅
- **Fix:** Resolved by removing `app/web/` entirely (see Section 2).

### 1.4 `app/pygame_ui/game_view.py:84-87` - AI moves bypass `perform_move()` ✅
- **Problem:** `execute_ai_turn()` manually manipulates `board.pieces` and `moves_made` instead of calling `game.perform_move()`, so AI moves are not logged to `move_log`.
- **Fix:** Replaced manual board manipulation with `self.game.perform_move()`. Also refactored `move_piece()` to delegate to `game.perform_move()`.

### 1.5 Test files - Wrong team name ✅
- **Fix:** Changed `'brown'` to `'black'` in `tests/test_integration.py`, `tests/test_api.py`, and `tests/test_storage.py`.

## 2. Remove Unused Code ✅ COMPLETE

### 2.1 Directories deleted
| Path | Status |
|------|--------|
| `app/web/` | ✅ Deleted - Incomplete Flask API; only referenced by `app/main.py` and `tests/test_api.py` |
| `app/rag/` | ⏭️ Kept per user request |
| `chroma_db/` | ⏭️ Kept per user request (used by RAG) |
| `assets/` | ⏭️ Kept per user request (used by RAG) |

### 2.2 Files deleted
| Path | Status |
|------|--------|
| `tests/network-policies.yaml` | ✅ Deleted - Exact duplicate of root file |
| `tests/test_api.py` | ✅ Deleted - Tests for removed web module |
| `PLAN.md` | ✅ Deleted - Completed development plan |
| `RAG_PLAN.md` | ✅ Deleted - Completed RAG plan |
| `app/main.py` | ✅ Deleted - Meta-entrypoint; redundant |
| `demo_rag.py` | ⏭️ Kept (RAG retained) |
| `demo_ui_integration.py` | ⏭️ Kept (RAG retained) |
| `requirements.txt` | ⏭️ Kept (RAG retained) |
| `tests/test_rag.py` | ⏭️ Kept (RAG retained) |
| `tests/test_state_formatter.py` | ⏭️ Kept (RAG retained) |

### 2.3 Clean `pyproject.toml` dependencies ✅
Removed unused dependencies:
- `flask`, `flask-cors` (only used by removed `app/web/`)
- `pyxel` (not imported anywhere in the codebase)

Kept (RAG retained):
- `langchain`, `langchain-community`, `langchain-ollama`, `chromadb`

**Tests: 122 passed (down from 143 — 21 removed with `test_api.py`)**

## 3. Fix UDS Deployment ✅ COMPLETE

### 3.1 Fix file paths ✅
- Updated `zarf.yaml` to reference root-level `deployment.yaml` and `network-policies.yaml` (removed `k8s/` prefix).

### 3.2 Fix `Dockerfile` ✅
- Updated base image from `python:3.11-slim` to `python:3.13-slim` (matches `pyproject.toml` requires-python).
- Changed dependency install from `requirements.txt` to `pyproject.toml` via `pip install .`.
- Changed CMD from `demo_ui_integration.py` (RAG demo) to `python -m app.rl.train --train --timesteps 100000 --no-render` (headless RL training).

### 3.3 Fix `deployment.yaml` ✅
- Removed `imagePullPolicy: Never` (incompatible with Zarf's in-cluster registry).
- Removed Ollama and ChromaDB deployments/services.
- Removed RAG-specific env vars (`OLLAMA_HOST`, `CHROMA_HOST`, `CHROMA_PORT`).
- Removed manual command override (uses Dockerfile CMD).
- Added resource requests/limits.

### 3.4 Fix `network-policies.yaml` ✅
- Removed Ollama and ChromaDB ingress policies.
- Simplified app egress to DNS-only (no external services needed for RL training).

### 3.5 Fix `zarf.yaml` ✅
- Removed `chromadb/chroma:latest` and `ollama/ollama:latest` from images list.
- Removed Ollama model pull actions from `onDeploy`.
- Replaced kubectl wait with proper `wait` action for deployment readiness.
- Updated description to remove "RAG" reference.

### 3.6 Create `uds-bundle.yaml` ✅
- Created the missing bundle file orchestrating: uds-k3d, Zarf init, UDS Core, and the app package.
- Follows the official UDS tutorial structure with proper overrides for Minio, Pepr, and Keycloak.

### 3.7 Rewrite `UDS_DEPLOYMENT.md` ✅
- Replaced manual kubectl workflow with proper UDS commands:
  1. `zarf package create --confirm`
  2. `uds create --confirm`
  3. `uds deploy uds-bundle-*.tar.zst --confirm`
- Removed k3d/kind conflict (k3d is handled by `uds-k3d` package).
- Removed Ollama model initialization steps.
- Added file reference table.

## 4. Update `CLAUDE.md`

After all changes, update `CLAUDE.md` to reflect:
- Removed modules (web)
- Removed dependencies
- Updated project structure
- Updated test counts
- Corrected deployment instructions

## Execution Order

1. ✅ Bug fixes (Section 1) - safe, no deletions
2. ✅ Remove unused code (Section 2) - delete files/dirs, clean deps
3. ✅ Fix UDS deployment (Section 3) - rewrite deployment configs
4. Update CLAUDE.md (Section 4) - reflect all changes
5. Run tests to verify nothing broke
6. ✅ `uv sync` to update lockfile after dep changes
