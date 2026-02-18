const BASE = '/api'

async function request(url, options = {}) {
  const res = await fetch(url, options)
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return data
}

export const createGame = (mode, difficulty) =>
  request(`${BASE}/game`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, difficulty }),
  })

export const makeMove = (id, from_pos, to_pos) =>
  request(`${BASE}/game/${id}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_pos, to_pos }),
  })

export const makePush = (id, piece, direction) =>
  request(`${BASE}/game/${id}/push`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ piece, direction }),
  })

export const skipMoves = (id) =>
  request(`${BASE}/game/${id}/skip-moves`, { method: 'POST' })

export const getValidMoves = (id, y, x) =>
  request(`${BASE}/game/${id}/valid-moves/${y}/${x}`)

export const getValidPushes = (id, y, x) =>
  request(`${BASE}/game/${id}/valid-pushes/${y}/${x}`)

export const saveGame = (id, filename) =>
  request(`${BASE}/game/${id}/save?filename=${encodeURIComponent(filename)}`, {
    method: 'POST',
  })

export const listSaves = () => request(`${BASE}/saves`)

export const loadSave = (id, filename) =>
  request(`${BASE}/game/${id}/load/${encodeURIComponent(filename)}`, {
    method: 'POST',
  })

export const askReferee = (id, question) =>
  request(`${BASE}/game/${id}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
