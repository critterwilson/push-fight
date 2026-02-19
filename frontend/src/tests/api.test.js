import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as api from '../api'

// ---------------------------------------------------------------------------
// fetch mock helpers
// ---------------------------------------------------------------------------

function mockFetch(body, ok = true) {
  global.fetch = vi.fn().mockResolvedValueOnce({
    ok,
    json: () => Promise.resolve(body),
  })
}

function mockFetchError(detail) {
  global.fetch = vi.fn().mockResolvedValueOnce({
    ok: false,
    json: () => Promise.resolve({ detail }),
  })
}

beforeEach(() => { vi.restoreAllMocks() })

// ---------------------------------------------------------------------------
// createGame
// ---------------------------------------------------------------------------

describe('createGame', () => {
  it('POSTs mode, difficulty and player_color, returns response', async () => {
    const response = { sessionId: 'abc123', state: { currentPlayer: 'white' } }
    mockFetch(response)

    const result = await api.createGame('pvp', 'medium')

    expect(fetch).toHaveBeenCalledWith('/api/game', expect.objectContaining({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'pvp', difficulty: 'medium', player_color: 'white' }),
    }))
    expect(result.sessionId).toBe('abc123')
  })

  it('POSTs player_color black when specified', async () => {
    mockFetch({ sessionId: 'xyz', state: {} })

    await api.createGame('pvai', 'medium', 'black')

    expect(fetch).toHaveBeenCalledWith('/api/game', expect.objectContaining({
      body: JSON.stringify({ mode: 'pvai', difficulty: 'medium', player_color: 'black' }),
    }))
  })

  it('throws on HTTP error', async () => {
    mockFetchError('Internal server error')
    await expect(api.createGame('pvp', 'medium')).rejects.toThrow('Internal server error')
  })
})

// ---------------------------------------------------------------------------
// makeMove
// ---------------------------------------------------------------------------

describe('makeMove', () => {
  it('POSTs from_pos and to_pos to correct URL', async () => {
    mockFetch({ success: true, state: {} })

    await api.makeMove('sid1', [4, 0], [3, 0])

    expect(fetch).toHaveBeenCalledWith('/api/game/sid1/move', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ from_pos: [4, 0], to_pos: [3, 0] }),
    }))
  })

  it('throws with server detail message on failure', async () => {
    mockFetchError('Invalid move destination')
    await expect(api.makeMove('sid1', [0, 0], [9, 9])).rejects.toThrow('Invalid move destination')
  })
})

// ---------------------------------------------------------------------------
// makePush
// ---------------------------------------------------------------------------

describe('makePush', () => {
  it('POSTs piece and direction', async () => {
    mockFetch({ success: true, state: {} })

    await api.makePush('sid1', [4, 0], [-1, 0])

    expect(fetch).toHaveBeenCalledWith('/api/game/sid1/push', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ piece: [4, 0], direction: [-1, 0] }),
    }))
  })
})

// ---------------------------------------------------------------------------
// skipMoves
// ---------------------------------------------------------------------------

describe('skipMoves', () => {
  it('POSTs to skip-moves endpoint', async () => {
    mockFetch({ success: true, state: {} })

    await api.skipMoves('sid1')

    expect(fetch).toHaveBeenCalledWith('/api/game/sid1/skip-moves', expect.objectContaining({
      method: 'POST',
    }))
  })
})

// ---------------------------------------------------------------------------
// getValidMoves / getValidPushes
// ---------------------------------------------------------------------------

describe('getValidMoves', () => {
  it('GETs valid moves for a piece', async () => {
    mockFetch({ moves: [[3, 0], [2, 1]] })

    const result = await api.getValidMoves('sid1', 4, 0)

    expect(fetch).toHaveBeenCalledWith('/api/game/sid1/valid-moves/4/0', expect.any(Object))
    expect(result.moves).toHaveLength(2)
  })
})

describe('getValidPushes', () => {
  it('GETs valid push directions for a piece', async () => {
    mockFetch({ directions: [[-1, 0], [0, 1]] })

    const result = await api.getValidPushes('sid1', 4, 0)

    expect(result.directions).toEqual([[-1, 0], [0, 1]])
  })
})

// ---------------------------------------------------------------------------
// saveGame / listSaves / loadSave
// ---------------------------------------------------------------------------

describe('saveGame', () => {
  it('POSTs to save endpoint with encoded filename', async () => {
    mockFetch({ saved: 'saves/my-game.json' })

    await api.saveGame('sid1', 'my-game')

    expect(fetch).toHaveBeenCalledWith(
      '/api/game/sid1/save?filename=my-game',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

describe('listSaves', () => {
  it('GETs saves list', async () => {
    mockFetch({ saves: ['game1', 'game2'] })

    const result = await api.listSaves()

    expect(fetch).toHaveBeenCalledWith('/api/saves', expect.any(Object))
    expect(result.saves).toEqual(['game1', 'game2'])
  })
})

describe('loadSave', () => {
  it('POSTs to load endpoint', async () => {
    mockFetch({ success: true, state: {} })

    await api.loadSave('sid1', 'game1')

    expect(fetch).toHaveBeenCalledWith(
      '/api/game/sid1/load/game1',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

// ---------------------------------------------------------------------------
// askReferee
// ---------------------------------------------------------------------------

describe('askReferee', () => {
  it('POSTs question to ask endpoint', async () => {
    mockFetch({ status: 'question submitted' })

    await api.askReferee('sid1', 'Can I move to a kill zone?')

    expect(fetch).toHaveBeenCalledWith('/api/game/sid1/ask', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ question: 'Can I move to a kill zone?' }),
    }))
  })
})
