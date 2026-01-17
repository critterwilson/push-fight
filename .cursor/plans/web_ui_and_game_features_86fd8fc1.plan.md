---
name: Web UI and Game Features
overview: Implement a web-based point-and-click UI using Angular frontend with Flask API backend, add JSON-based save/load functionality, and create a custom piece placement system that enforces game rules (3 squares + 2 rounds per team).
todos:
  - id: serialization
    content: Add to_dict/from_dict methods to Piece, PushFightBoard, and GameState classes for JSON serialization
    status: completed
  - id: storage
    content: Create storage module with save/load functions for JSON game files
    status: completed
    dependencies:
      - serialization
  - id: placement
    content: Add custom piece placement methods to GameState with rule enforcement (3 squares + 2 rounds per team)
    status: completed
  - id: flask-app
    content: Create Flask application structure (app.py, routes.py) with API endpoints
    status: completed
    dependencies:
      - serialization
      - placement
  - id: frontend-html
    content: Build HTML template with game board grid, controls, and modals
    status: completed
  - id: frontend-js
    content: Implement TypeScript/Angular logic for board interactions, click handlers, API communication, and piece placement UI
    status: completed
    dependencies:
      - frontend-html
      - flask-app
  - id: frontend-css
    content: Create CSS styling for Angular components (board, pieces, modals, UI components)
    status: completed
    dependencies:
      - frontend-html
  - id: push-ui
    content: Add push direction selection UI (direction buttons or adjacent cell click) and push phase detection
    status: completed
    dependencies:
      - frontend-js
  - id: frontend-setup
    content: Set up Angular project structure, dependencies, and build configuration
    status: completed
  - id: main-integration
    content: Update main.py to support both CLI and web server modes
    status: completed
    dependencies:
      - flask-app
  - id: dependencies
    content: Update pyproject.toml with Flask dependencies
    status: completed
  - id: todo-1768679843101-yxkjrtpxl
    content: Build full test suite
    status: completed
  - id: frontend-tests
    content: Create Angular component and service unit tests
    status: completed
    dependencies:
      - frontend-js
  - id: push-phase-detection
    content: Add push phase detection (when moves_made >= 2 or can_move is false)
    status: completed
    dependencies:
      - frontend-js
  - id: push-direction-ui
    content: Add push direction selection UI (direction buttons and adjacent cell click)
    status: completed
    dependencies:
      - push-phase-detection
  - id: push-visual-indicators
    content: Add visual indicators for push phase vs move phase
    status: completed
    dependencies:
      - push-phase-detection
  - id: todo-1768680445243-tezxatyna
    content: Build a tmuxinator script to run the UI and backend of the game locally
    status: completed
  - id: todo-1768680463102-2af6tx83c
    content: ""
    status: cancelled
---

# Implementation Plan: Web UI, Save/Load, and Custom Piece Placement

## Architecture Overview

The implementation will add:

1. **Web-based UI** using Angular frontend (SPA) with Flask API backend for point-and-click gameplay
2. **JSON save/load** system for game state persistence
3. **Custom piece placement** interface with rule enforcement

**Architecture:**

- **Backend**: Flask REST API (Python) - serves API endpoints only
- **Frontend**: Angular SPA (TypeScript) - separate application that communicates with Flask API
- **Development**: Angular dev server (port 4200) with proxy to Flask API (port 5000)
- **Production**: Angular build served by Flask or separate web server

## Component Structure

```
app/
├── engine/           # Existing game logic
├── web/              # Flask API backend
│   ├── __init__.py
│   ├── app.py        # Flask application
│   ├── routes.py     # API endpoints
│   └── templates/    # Fallback template (dev only)
│       └── index.html
├── storage/          # Save/load functionality
│   ├── __init__.py
│   └── game_storage.py
└── main.py           # Update: Add web server option

frontend/             # NEW: Angular SPA
├── src/
│   ├── app/
│   │   ├── components/
│   │   │   ├── game-board/
│   │   │   ├── game-status/
│   │   │   ├── game-controls/
│   │   │   ├── setup-panel/
│   │   │   ├── save-modal/
│   │   │   ├── load-modal/
│   │   │   └── game-over-modal/
│   │   ├── services/
│   │   │   └── game.service.ts
│   │   └── app.component.ts
│   ├── index.html
│   ├── main.ts
│   └── styles.css
├── angular.json
├── package.json
├── tsconfig.json
└── proxy.conf.json
```

## Implementation Details

### 1. Serialization System (`app/engine/game_state.py`, `app/engine/board.py`, `app/engine/pieces.py`)

Add serialization methods to existing classes:

- **`Piece.to_dict()`** and **`Piece.from_dict()`**: Convert Piece objects to/from dictionaries
- **`PushFightBoard.to_dict()`** and **`PushFightBoard.from_dict()`**: Serialize board state including grid, pieces array, and anchor position
- **`GameState.to_dict()`** and **`GameState.from_dict()`**: Serialize complete game state
- **`GameState.save_to_file(path)`** and **`GameState.load_from_file(path)`**: File I/O helpers

### 2. Custom Piece Placement (`app/engine/game_state.py`)

Add new methods for setup phase:

- **`GameState.create_custom_game()`**: Create empty game state for setup
- **`GameState.place_piece(y, x, team, shape)`**: Place a piece during setup with validation
- **`GameState.get_placement_status(team)`**: Returns dict with counts: `{'squares': 0, 'rounds': 0, 'total': 0}`
- **`GameState.can_start_game()`**: Validates both teams have exactly 3 squares and 2 rounds
- **`GameState.start_game()`**: Transitions from setup to active game

### 3. Web API (`app/web/routes.py`)

Flask API endpoints:

- **`GET /api/game/state`**: Get current game state (JSON)
- **`POST /api/game/new`**: Create new game (with optional custom placement flag)
- **`POST /api/game/move`**: Move a piece `{"from": [y, x], "to": [y, x]}`
- **`POST /api/game/push`**: Perform push `{"piece": [y, x], "direction": [dy, dx]}`
- **`POST /api/game/place`**: Place piece during setup `{"y": int, "x": int, "team": str, "shape": str}`
- **`POST /api/game/remove`**: Remove piece during setup `{"y": int, "x": int}`
- **`POST /api/game/start`**: Start game after placement
- **`GET /api/game/valid-moves`**: Get valid moves for a piece `?y=4&x=2`
- **`POST /api/game/save`**: Save game `{"filename": "game1.json"}`
- **`GET /api/game/saves`**: List saved games
- **`POST /api/game/load`**: Load game `{"filename": "game1.json"}`

### 4. Angular Frontend (`frontend/`)

**Project Structure:**

- **Angular Standalone Components** architecture
- **TypeScript** for type safety
- **RxJS Observables** for reactive state management
- **Component-based** UI architecture

**Components:**

- **`app.component.ts`**: Root component orchestrating all child components
- **`game-board.component.ts`**: 10x4 game board with:
  - Visual representation of pieces, kill zones, anchor
  - Click handling for moves and setup
  - Highlighting for selected pieces and valid moves
- **`game-status.component.ts`**: Displays current player, moves made, game phase
- **`game-controls.component.ts`**: Control buttons (New Game, Save, Load)
- **`setup-panel.component.ts`**: Piece placement interface with inventory and controls
- **`save-modal.component.ts`**: Modal for saving games
- **`load-modal.component.ts`**: Modal for loading games
- **`game-over-modal.component.ts`**: Game over notification

**Services:**

- **`game.service.ts`**: Centralized API communication service
  - Observable-based state management
  - All API endpoint methods
  - Selection and valid moves management

**Styling:**

- Component-scoped CSS
- Responsive design
- Visual feedback for game interactions

### 5. Flask Application (`app/web/app.py`)

- Initialize Flask app
- Register routes from `routes.py`
- Serve Angular app in production (from `dist/` folder)
- CORS support for Angular frontend
- Error handling middleware

### 6. Storage System (`app/storage/game_storage.py`)

- **`save_game(game_state, filename)`**: Save to `saves/` directory
- **`load_game(filename)`**: Load from `saves/` directory
- **`list_saves()`**: Get list of available save files
- **`delete_save(filename)`**: Remove save file
- Create `saves/` directory if it doesn't exist

### 7. Updated Entry Point (`app/main.py`)

Added command-line argument parsing to support both modes:

**CLI Mode (default):**

- `uv run python -m app.main` → Play game in terminal
- `python -m app.main` → Same (interactive CLI game)

**Web Server Mode:**

- `uv run python -m app.main --web` → Start Flask API server (default: port 5000)
- `uv run python -m app.main --web --host 127.0.0.1 --port 8080` → Custom host/port
- `uv run python -m app.main --web --debug` → Enable Flask debug mode

**Development Workflow:**

1. Start Flask API: `uv run python -m app.main --web` (port 5000)
2. Start Angular dev server: `cd frontend && npm start` (port 4200)
3. Angular proxy forwards `/api/*` requests to Flask

**Production:**

- Build Angular: `cd frontend && npm run build`
- Start Flask: `uv run python -m app.main --web`
- Flask serves Angular app from `frontend/dist/push-fight-frontend/browser/`

## Dependencies

**Backend (`pyproject.toml`):**

- `flask>=3.0.0` - Web framework
- `flask-cors>=4.0.0` - CORS support for Angular frontend

**Frontend (`frontend/package.json`):**

- `@angular/core>=17.0.0` - Angular framework
- `@angular/common>=17.0.0` - Common Angular modules
- `@angular/forms>=17.0.0` - Forms module
- `rxjs>=7.8.0` - Reactive programming
- `zone.js>=0.14.0` - Angular change detection
- `@angular/cli>=17.0.0` - Angular CLI (dev dependency)

**Frontend Testing (`frontend/package.json` devDependencies):**

- `jasmine-core>=5.1.0` - Testing framework
- `karma>=6.4.0` - Test runner
- `karma-jasmine>=5.1.0` - Karma Jasmine adapter
- `karma-chrome-launcher>=3.2.0` - Chrome launcher for tests
- `karma-coverage>=2.2.0` - Code coverage
- `@types/jasmine>=5.1.0` - Jasmine type definitions

## File Changes Summary

**New Files:**

**Backend:**

- `app/web/__init__.py`
- `app/web/app.py`
- `app/web/routes.py`
- `app/web/templates/index.html` (fallback for dev)
- `app/storage/__init__.py`
- `app/storage/game_storage.py`

**Frontend:**

- `frontend/package.json`
- `frontend/angular.json`
- `frontend/tsconfig.json`
- `frontend/tsconfig.app.json`
- `frontend/proxy.conf.json`
- `frontend/src/index.html`
- `frontend/src/main.ts`
- `frontend/src/styles.css`
- `frontend/src/app/app.component.ts`
- `frontend/src/app/services/game.service.ts`
- `frontend/src/app/components/game-board/game-board.component.ts`
- `frontend/src/app/components/game-status/game-status.component.ts`
- `frontend/src/app/components/game-controls/game-controls.component.ts`
- `frontend/src/app/components/setup-panel/setup-panel.component.ts`
- `frontend/src/app/components/save-modal/save-modal.component.ts`
- `frontend/src/app/components/load-modal/load-modal.component.ts`
- `frontend/src/app/components/game-over-modal/game-over-modal.component.ts`
- `frontend/src/app/components/game-over-modal/game-over-modal.component.spec.ts`
- `frontend/src/app/app.component.spec.ts`
- `frontend/karma.conf.js`
- `frontend/tsconfig.spec.json`
- `frontend/README.md`

**Push Phase Features:**

- Push phase detection in GameService (`isPushPhase$`, `canMove$` observables)
- Push direction selection UI in GameBoardComponent (direction buttons + adjacent cell click)
- Visual indicators (push phase banner, phase label highlighting, push target cells)

**Modified Files:**

- `app/engine/pieces.py` - Add serialization methods
- `app/engine/board.py` - Add serialization methods
- `app/engine/game_state.py` - Add serialization, custom placement methods
- `app/main.py` - Add web server option
- `pyproject.toml` - Add Flask dependencies and pytest dev dependencies
- `README.md` - Add setup instructions
- `tests/__init__.py` - Test package initialization
- `tests/conftest.py` - Pytest configuration
- `pytest.ini` - Pytest settings
- `frontend/src/app/services/game.service.ts` - Added push phase observables and auto-mode detection
- `frontend/src/app/components/game-board/game-board.component.ts` - Added push UI, direction buttons, phase detection
- `frontend/src/app/components/game-status/game-status.component.ts` - Added push phase label highlighting

## Implementation Order

1. ✅ Add serialization methods to engine classes
2. ✅ Implement storage system
3. ✅ Create Flask app structure and basic routes
4. ✅ Add custom piece placement logic
5. ✅ Build Angular frontend structure and components
6. ✅ Implement TypeScript/Angular logic for board interactions (move, setup, API communication)
7. ✅ Create CSS styling for components (inline styles in all components)
8. ✅ Integrate save/load UI (modals implemented and connected)
9. ✅ Add push direction selection UI and push phase detection
10. ✅ Build comprehensive test suite (61 tests covering engine, storage, API, and integration)
11. ✅ Create Angular component and service unit tests (9 test files covering all components and GameService)
12. ✅ Update main.py for web server mode
13. ✅ Add push phase detection (automatic detection when moves_made >= 2)
14. ✅ Add push direction selection UI (direction buttons and adjacent cell click support)
15. ✅ Add visual indicators for push phase (banner, phase label, push target highlighting)