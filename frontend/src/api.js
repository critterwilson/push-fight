/**
 * REST API client for the Push Fight backend.
 *
 * Every exported function maps 1:1 to a backend endpoint.  All calls
 * go through the shared `request()` helper which handles JSON parsing
 * and error extraction.
 *
 * The base path '/api' is relative — Vite's dev server proxies it to
 * the FastAPI backend, and in production the SPA is served from the
 * same origin as the API.
 *
 * API surface:
 *   Game lifecycle:  createGame, makeMove, makePush, skipMoves
 *   Board queries:   getValidMoves, getValidPushes
 *   Persistence:     saveGame, listSaves, loadSave
 *   RAG referee:     askReferee
 *   Setup phase:     setupPlace, setupRemove, setupConfirm
 */

const BASE = '/api'

/**
 * Shared request helper — sends a fetch, parses JSON, and throws
 * on non-OK responses with the server's error detail message.
 */
async function request(url, options = {}) {
  const res = await fetch(url, options)
  let data
  try {
    data = await res.json()
  } catch {
    throw new Error(`HTTP ${res.status}: ${res.statusText || 'Server error'}`)
  }
  if (!res.ok) {
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return data
}

// ---------------------------------------------------------------------------
// Game lifecycle
// ---------------------------------------------------------------------------

/** Create a new game session with the given mode/difficulty/color. */
export const createGame = (mode, difficulty, playerColor = 'white') =>
  request(`${BASE}/game`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, difficulty, player_color: playerColor }),
  })

/** Slide a piece from `from_pos` [y,x] to `to_pos` [y,x]. */
export const makeMove = (id, from_pos, to_pos) =>
  request(`${BASE}/game/${id}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_pos, to_pos }),
  })

/** Push with a square piece at `piece` [y,x] in `direction` [dy,dx]. */
export const makePush = (id, piece, direction) =>
  request(`${BASE}/game/${id}/push`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ piece, direction }),
  })

/** Skip remaining moves and advance to push phase. */
export const skipMoves = (id) =>
  request(`${BASE}/game/${id}/skip-moves`, { method: 'POST' })

// ---------------------------------------------------------------------------
// Board queries
// ---------------------------------------------------------------------------

/** Get all valid move destinations for the piece at (y, x). */
export const getValidMoves = (id, y, x) =>
  request(`${BASE}/game/${id}/valid-moves/${y}/${x}`)

/** Get all valid push directions for the square piece at (y, x). */
export const getValidPushes = (id, y, x) =>
  request(`${BASE}/game/${id}/valid-pushes/${y}/${x}`)

// ---------------------------------------------------------------------------
// Persistence (save/load)
// ---------------------------------------------------------------------------

/** Save the current game state to a named file on the server. */
export const saveGame = (id, filename) =>
  request(`${BASE}/game/${id}/save?filename=${encodeURIComponent(filename)}`, {
    method: 'POST',
  })

/** List all available save file names. */
export const listSaves = () => request(`${BASE}/saves`)

/** Load a previously saved game into the current session. */
export const loadSave = (id, filename) =>
  request(`${BASE}/game/${id}/load/${encodeURIComponent(filename)}`, {
    method: 'POST',
  })

// ---------------------------------------------------------------------------
// RAG referee
// ---------------------------------------------------------------------------

/** Submit a question to the AI referee (answer arrives via WebSocket). */
export const askReferee = (id, question) =>
  request(`${BASE}/game/${id}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

// ---------------------------------------------------------------------------
// Setup phase
// ---------------------------------------------------------------------------

/** Place a named piece at (y, x) during the setup phase. */
export const setupPlace = (id, y, x, name) =>
  request(`${BASE}/game/${id}/setup/place`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ y, x, name }),
  })

/** Remove a placed piece at (y, x) during setup (undo). */
export const setupRemove = (id, y, x) =>
  request(`${BASE}/game/${id}/setup/${y}/${x}`, { method: 'DELETE' })

/** Confirm the current team's placement and advance setup. */
export const setupConfirm = (id) =>
  request(`${BASE}/game/${id}/setup/confirm`, { method: 'POST' })
