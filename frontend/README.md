# Frontend — React Web UI

Single-page React application for playing Push Fight in the browser. Communicates with the FastAPI backend via REST and WebSocket.

## Files

| File | Purpose |
|------|---------|
| `App.jsx` | Root component — game creation, layout, theme/mode state |
| `Board.jsx` | SVG board rendering — pieces, highlights, kill zones, anchor marker |
| `GameControls.jsx` | Move/push/skip/save buttons and AI difficulty selector |
| `StatusBar.jsx` | Current turn, phase, and score display |
| `ChatPanel.jsx` | RAG referee chat interface — question input and answer display |
| `ThemeToggle.jsx` | Light/dark mode toggle button |
| `TutorialModal.jsx` | Rules tutorial modal |
| `ErrorBoundary.jsx` | React error boundary for graceful failure |
| `useGame.js` | Custom hook — game state management, REST calls, WebSocket connection |
| `useVoiceControl.js` | Custom hook — Web Speech API for voice commands |
| `api.js` | API client — fetch wrappers for all REST endpoints |
| `index.css` | Global styles, BJJ belt color palette, light/dark theme variables |
| `main.jsx` | React entry point |

---

## Running

```bash
cd frontend
npm install
npm run dev       # http://localhost:3000 (dev server with HMR)
```

The Vite dev server proxies `/api` and `/ws` to `http://localhost:8000` (see `vite.config.js`).

### Other commands

```bash
npm run build     # Production build -> dist/
npm run preview   # Preview production build locally
npm test          # Run tests once (vitest)
npm run test:watch # Run tests in watch mode
```

---

## Architecture

The frontend is structured around a single `useGame` hook that manages all game state:

```
App.jsx
  |-- useGame.js          (state + WebSocket + REST calls)
  |-- useVoiceControl.js  (speech recognition -> game actions)
  |
  |-- Board.jsx           (SVG rendering)
  |-- GameControls.jsx    (action buttons)
  |-- StatusBar.jsx       (turn/phase display)
  |-- ChatPanel.jsx       (RAG referee)
  |-- TutorialModal.jsx   (rules modal)
```

`useGame` maintains a WebSocket connection to `/ws/{sessionId}` and updates state on every `state_update` event. User actions (move, push, skip) are sent via REST and the resulting state arrives via WebSocket broadcast.

---

## Styling

CSS variables in `index.css` define the BJJ belt color palette:

| Variable | Usage |
|----------|-------|
| `--belt-white` | White team pieces |
| `--belt-blue` | UI accents |
| `--belt-purple` | Interactive highlights |
| `--belt-brown` | Board wood texture |
| `--belt-black` | Black team pieces |

Light/dark mode is toggled via `[data-theme="dark"]` on the `<html>` element. Prefer theme variables (`--bg-input`, `--btn-ghost-h`, etc.) over hardcoded hex values.

---

## Voice Control

`useVoiceControl.js` uses the Web Speech API (Chrome/Edge) to recognize commands:

- **Move:** `"sleeve to b4"` — piece name + destination coordinate
- **Push:** `"lapel push down"` — piece name + push direction
- **Skip:** `"skip"` — end move phase

The grammar uses actual piece names (sleeve, lapel, belt, neck, joint) parsed from `gameState.currentPlayer`'s pieces.

> **Note:** The serialized game state uses **camelCase** (`currentPlayer`, not `current_player`). Always use camelCase when reading frontend game state fields.

---

## Testing

Tests use **vitest** with **jsdom** and **@testing-library/react**.

```bash
npm test              # single run
npm run test:watch    # watch mode
```

Config in `vite.config.js`:
```js
test: {
  environment: 'jsdom',
  setupFiles: ['./src/tests/setup.js'],
  globals: true,
}
```

Test files live in `src/tests/`.
