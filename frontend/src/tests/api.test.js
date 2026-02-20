/**
 * Tests for the API client module (frontend/src/api.js).
 *
 * The api module provides thin async wrappers around the Push Fight server's
 * REST endpoints. Each function constructs the correct fetch() call (URL,
 * method, headers, body) and handles error responses by throwing with the
 * server's detail message.
 *
 * Testing strategy:
 *   - global.fetch is mocked before each test using helper functions
 *     (mockFetch for success, mockFetchError for failure).
 *   - Tests verify the exact URL, method, headers, and JSON body passed
 *     to fetch() for each API function.
 *   - Error handling is tested by mocking a non-ok response and asserting
 *     that the function rejects with the server's error detail.
 *   - vi.restoreAllMocks() runs before each test to prevent mock leakage.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as api from '../api'

// ---------------------------------------------------------------------------
// fetch mock helpers
// ---------------------------------------------------------------------------

/**
 * Mock global.fetch to resolve with {ok: true, json: () => body}.
 * Use this for testing successful API responses.
 */
function mockFetch(body, ok = true) {
  global.fetch = vi.fn().mockResolvedValueOnce({
    ok,
    json: () => Promise.resolve(body),
  })
}

/**
 * Mock global.fetch to resolve with {ok: false, json: () => {detail}}.
 * Use this for testing error responses — the API functions should throw
 * with the detail message.
 */
function mockFetchError(detail) {
  global.fetch = vi.fn().mockResolvedValueOnce({
    ok: false,
    json: () => Promise.resolve({ detail }),
  })
}

/** Reset all mocks between tests to prevent state leakage. */
beforeEach(() => { vi.restoreAllMocks() })

// ---------------------------------------------------------------------------
// createGame
// ---------------------------------------------------------------------------

describe('createGame', () => {
  /** Tests for api.createGame(mode, difficulty, playerColor).
   *  This endpoint creates a new game session on the server and returns
   *  the sessionId + initial game state. */

  it('POSTs mode, difficulty and player_color, returns response', async () => {
    /** Default player_color is 'white'. Verify the fetch call includes all
     *  three parameters and the response is returned as-is. */
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
    /** When the player chooses to play as black, the player_color parameter
     *  must be 'black' in the request body. */
    mockFetch({ sessionId: 'xyz', state: {} })

    await api.createGame('pvai', 'medium', 'black')

    expect(fetch).toHaveBeenCalledWith('/api/game', expect.objectContaining({
      body: JSON.stringify({ mode: 'pvai', difficulty: 'medium', player_color: 'black' }),
    }))
  })

  it('throws on HTTP error', async () => {
    /** When the server returns a non-ok status, createGame must throw an
     *  Error with the server's detail message for UI error handling. */
    mockFetchError('Internal server error')
    await expect(api.createGame('pvp', 'medium')).rejects.toThrow('Internal server error')
  })
})

// ---------------------------------------------------------------------------
// makeMove
// ---------------------------------------------------------------------------

describe('makeMove', () => {
  /** Tests for api.makeMove(sessionId, fromPos, toPos).
   *  Sends a piece movement request with source and destination coordinates. */

  it('POSTs from_pos and to_pos to correct URL', async () => {
    /** Verify the URL includes the session ID and the body contains the
     *  from_pos and to_pos coordinate arrays. */
    mockFetch({ success: true, state: {} })

    await api.makeMove('sid1', [4, 0], [3, 0])

    expect(fetch).toHaveBeenCalledWith('/api/game/sid1/move', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ from_pos: [4, 0], to_pos: [3, 0] }),
    }))
  })

  it('throws with server detail message on failure', async () => {
    /** When the move is illegal, the server returns a detail message that
     *  the API client must surface as a thrown Error. */
    mockFetchError('Invalid move destination')
    await expect(api.makeMove('sid1', [0, 0], [9, 9])).rejects.toThrow('Invalid move destination')
  })
})

// ---------------------------------------------------------------------------
// makePush
// ---------------------------------------------------------------------------

describe('makePush', () => {
  /** Tests for api.makePush(sessionId, piece, direction).
   *  Sends a push action with the pushing piece's position and direction vector. */

  it('POSTs piece and direction', async () => {
    /** Verify the request body contains piece=[y,x] and direction=[dy,dx]. */
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
  /** Tests for api.skipMoves(sessionId).
   *  Skips the optional move phase and transitions directly to push phase. */

  it('POSTs to skip-moves endpoint', async () => {
    /** Verify the correct URL is called with POST method. No request body
     *  is needed for skip-moves. */
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
  /** Tests for api.getValidMoves(sessionId, y, x).
   *  Fetches the list of valid slide destinations for a piece at (y, x). */

  it('GETs valid moves for a piece', async () => {
    /** Verify the URL encodes the piece coordinates and the response
     *  contains the moves array from the server. */
    mockFetch({ moves: [[3, 0], [2, 1]] })

    const result = await api.getValidMoves('sid1', 4, 0)

    expect(fetch).toHaveBeenCalledWith('/api/game/sid1/valid-moves/4/0', expect.any(Object))
    expect(result.moves).toHaveLength(2)
  })
})

describe('getValidPushes', () => {
  /** Tests for api.getValidPushes(sessionId, y, x).
   *  Fetches the list of valid push directions for a square piece at (y, x). */

  it('GETs valid push directions for a piece', async () => {
    /** Verify the response contains the directions array of [dy, dx] vectors. */
    mockFetch({ directions: [[-1, 0], [0, 1]] })

    const result = await api.getValidPushes('sid1', 4, 0)

    expect(result.directions).toEqual([[-1, 0], [0, 1]])
  })
})

// ---------------------------------------------------------------------------
// saveGame / listSaves / loadSave
// ---------------------------------------------------------------------------

describe('saveGame', () => {
  /** Tests for api.saveGame(sessionId, filename).
   *  Persists the current game state to a named file on the server. */

  it('POSTs to save endpoint with encoded filename', async () => {
    /** The filename must be passed as a query parameter, not in the body,
     *  to match the server's endpoint signature. */
    mockFetch({ saved: 'saves/my-game.json' })

    await api.saveGame('sid1', 'my-game')

    expect(fetch).toHaveBeenCalledWith(
      '/api/game/sid1/save?filename=my-game',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

describe('listSaves', () => {
  /** Tests for api.listSaves().
   *  Retrieves the list of all saved game filenames from the server. */

  it('GETs saves list', async () => {
    /** Verify the correct URL is called and the saves array is returned. */
    mockFetch({ saves: ['game1', 'game2'] })

    const result = await api.listSaves()

    expect(fetch).toHaveBeenCalledWith('/api/saves', expect.any(Object))
    expect(result.saves).toEqual(['game1', 'game2'])
  })
})

describe('loadSave', () => {
  /** Tests for api.loadSave(sessionId, saveName).
   *  Loads a previously saved game into the current session. */

  it('POSTs to load endpoint', async () => {
    /** The save name is part of the URL path, not the request body. */
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
  /** Tests for api.askReferee(sessionId, question).
   *  Sends a natural-language question to the RAG-powered AI referee. The
   *  response is delivered asynchronously via WebSocket (rag_answer event),
   *  not in the HTTP response — so we only verify the POST was sent correctly. */

  it('POSTs question to ask endpoint', async () => {
    /** The question must be sent as JSON in the request body. The server
     *  returns a status acknowledgment; the actual answer comes over WebSocket. */
    mockFetch({ status: 'question submitted' })

    await api.askReferee('sid1', 'Can I move to a kill zone?')

    expect(fetch).toHaveBeenCalledWith('/api/game/sid1/ask', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ question: 'Can I move to a kill zone?' }),
    }))
  })
})
