/**
 * Tests for the useGame React hook (frontend/src/useGame.js).
 *
 * The useGame hook is the central state-management layer for the Push Fight
 * frontend. It handles:
 *   - Game session creation (via fetch to POST /api/game).
 *   - WebSocket connection lifecycle (connect, reconnect, close).
 *   - Real-time state updates from the server (state_update events).
 *   - AI action visualization (ai_action / ai_done events).
 *   - RAG referee Q&A (askReferee + rag_answer events).
 *   - User interactions (handleCellClick for piece selection and movement).
 *
 * Testing strategy:
 *   - WebSocket is stubbed with MockWebSocket, which records instances and
 *     provides an emit() helper to simulate server messages.
 *   - fetch is mocked per-test to control API responses.
 *   - vi.useFakeTimers() is used to test time-dependent behavior like
 *     WebSocket reconnection delays.
 *   - renderHook from @testing-library/react is used to mount the hook in
 *     isolation (no wrapping component needed).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useGame } from '../useGame'

// ---------------------------------------------------------------------------
// Mock WebSocket (no actual connections in tests)
// ---------------------------------------------------------------------------

/**
 * Minimal WebSocket stub that records all created instances and provides
 * an emit() helper to simulate incoming server messages.
 * - constructor: records the URL and marks readyState as OPEN (1).
 * - send/close: no-ops (close triggers onclose with code 1000).
 * - emit(data): serializes data as JSON and calls onmessage.
 */
class MockWebSocket {
  constructor(url) {
    this.url      = url
    this.readyState = 1 // OPEN
    MockWebSocket.instances.push(this)
  }
  send()  {}
  close() { this.onclose?.({ code: 1000 }) }
  /** Simulate a server-sent message by calling onmessage with JSON data. */
  emit(data) { this.onmessage?.({ data: JSON.stringify(data) }) }
}
/** Track all MockWebSocket instances created during a test. */
MockWebSocket.instances = []

// ---------------------------------------------------------------------------
// Mock fetch
// ---------------------------------------------------------------------------

/**
 * The initial game state returned by the createGame API call.
 * Represents an empty 10x4 board in PvP mode, white to move, no pieces.
 */
const INITIAL_STATE = {
  sessionId: 'sess-1',
  state: {
    board: Array.from({ length: 10 }, (_, y) =>
      Array.from({ length: 4 }, (_, x) => ({
        y, x, killZone: y === 0 || y === 9, piece: null, isAnchor: false,
      }))
    ),
    currentPlayer: 'white',
    canMove: true,
    canPush: false,
    pushCompleted: false,
    gameOver: false,
    winner: null,
    isAiTurn: false,
    mode: 'pvp',
    aiTeam: null,
    movesMade: 0,
    piecesPushedOff: { white: { squares: 0, rounds: 0 }, black: { squares: 0, rounds: 0 } },
  },
}

/** Mock global.fetch to resolve with the given body. */
function mockFetch(body, ok = true) {
  global.fetch = vi.fn().mockResolvedValueOnce({
    ok, json: () => Promise.resolve(body),
  })
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  /** Reset WebSocket instance tracking and install the mock. Use fake
   *  timers to control reconnection delay behavior. */
  MockWebSocket.instances = []
  global.WebSocket = MockWebSocket
  vi.useFakeTimers()
})

afterEach(() => {
  /** Restore all mocks and switch back to real timers after each test. */
  vi.restoreAllMocks()
  vi.useRealTimers()
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useGame — initial state', () => {
  /** Before any game is created, the hook should be in a clean idle state
   *  with no session, no game state, no AI activity, and no messages. */

  it('starts with no session and no game state', () => {
    /** Verify all initial values are null/false/empty to confirm the hook
     *  doesn't attempt any API calls or WebSocket connections on mount. */
    const { result } = renderHook(() => useGame())
    expect(result.current.sessionId).toBeNull()
    expect(result.current.gameState).toBeNull()
    expect(result.current.connectionStatus).toBe('idle')
    expect(result.current.aiThinking).toBe(false)
    expect(result.current.messages).toHaveLength(0)
  })
})

describe('useGame — createGame', () => {
  /** Tests for the createGame flow: API call, state initialization, WebSocket
   *  connection establishment, and error handling on API failure. */

  it('sets sessionId and gameState after createGame', async () => {
    /** After a successful createGame call, the hook must store the session
     *  ID and populate the game state from the API response. */
    mockFetch(INITIAL_STATE)
    const { result } = renderHook(() => useGame())

    await act(async () => {
      await result.current.createGame('pvp', 'medium')
    })

    expect(result.current.sessionId).toBe('sess-1')
    expect(result.current.gameState).not.toBeNull()
    expect(result.current.gameState.currentPlayer).toBe('white')
  })

  it('opens a WebSocket connection after session is created', async () => {
    /** The hook must automatically establish a WebSocket connection to
     *  /ws/{sessionId} for real-time state updates after game creation. */
    mockFetch(INITIAL_STATE)
    const { result } = renderHook(() => useGame())

    await act(async () => {
      await result.current.createGame('pvp', 'medium')
    })

    expect(MockWebSocket.instances).toHaveLength(1)
    expect(MockWebSocket.instances[0].url).toContain('/ws/sess-1')
  })

  it('shows error and does not set sessionId on API failure', async () => {
    /** When the createGame API call fails, the hook must set an error
     *  message and leave sessionId as null so the UI can display an error
     *  state rather than attempting to connect via WebSocket. */
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Server error' }),
    })
    const { result } = renderHook(() => useGame())

    await act(async () => {
      await result.current.createGame('pvp', 'medium')
    })

    expect(result.current.sessionId).toBeNull()
    expect(result.current.error).toBe('Server error')
  })
})

describe('useGame — WebSocket events', () => {
  async function setupSession() {
    mockFetch(INITIAL_STATE)
    const hook = renderHook(() => useGame())
    await act(async () => { await hook.result.current.createGame('pvp', 'medium') })
    const ws = MockWebSocket.instances[0]
    return { hook, ws }
  }

  it('updates gameState on state_update event', async () => {
    const { hook, ws } = await setupSession()
    const newState = { ...INITIAL_STATE.state, currentPlayer: 'black' }

    act(() => { ws.emit({ event: 'state_update', state: newState }) })

    expect(hook.result.current.gameState.currentPlayer).toBe('black')
  })

  it('sets aiThinking on ai_action event and clears on ai_done', async () => {
    const { hook, ws } = await setupSession()

    act(() => { ws.emit({ event: 'ai_action', action: { type: 'move', from: [5,0], to: [4,0] } }) })
    expect(hook.result.current.aiThinking).toBe(true)
    expect(hook.result.current.pendingAiAction).toMatchObject({ type: 'move' })

    act(() => { ws.emit({ event: 'ai_done' }) })
    expect(hook.result.current.aiThinking).toBe(false)
    expect(hook.result.current.pendingAiAction).toBeNull()
  })

  it('appends rag_answer to messages and replaces loading placeholder', async () => {
    const { hook, ws } = await setupSession()

    // Simulate the loading placeholder that askReferee adds
    act(() => {
      hook.result.current.askReferee('Is this a valid move?')
    })
    // Mock the fetch for askReferee
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true, json: () => Promise.resolve({ status: 'question submitted' }),
    })

    await act(async () => {
      ws.emit({ event: 'rag_answer', answer: 'Yes, that is valid.' })
    })

    const msgs = hook.result.current.messages
    expect(msgs.some(m => m.text === 'Yes, that is valid.')).toBe(true)
    expect(msgs.some(m => m.loading)).toBe(false)
  })

  it('attempts reconnect after unexpected close', async () => {
    const { hook, ws } = await setupSession()

    act(() => { ws.onclose({ code: 1006 }) }) // abnormal close
    expect(hook.result.current.connectionStatus).toBe('disconnected')

    // Advance past the 2-second reconnect delay
    act(() => { vi.advanceTimersByTime(2500) })

    // A new WS instance should have been created
    expect(MockWebSocket.instances.length).toBeGreaterThan(1)
  })

  it('does not reconnect on session-expired close (code 4004)', async () => {
    const { hook, ws } = await setupSession()
    const instancesBefore = MockWebSocket.instances.length

    act(() => { ws.onclose({ code: 4004 }) })

    // Error should be visible immediately (before the auto-clear timer fires)
    expect(hook.result.current.error).toBeTruthy()

    // Advance past the 2-second reconnect delay — still no new WS
    act(() => { vi.advanceTimersByTime(2500) })
    expect(MockWebSocket.instances.length).toBe(instancesBefore)
  })
})

describe('useGame — handleCellClick in move phase', () => {
  it('fetches valid moves when an own piece is clicked', async () => {
    mockFetch(INITIAL_STATE) // createGame
    const hook = renderHook(() => useGame())

    await act(async () => { await hook.result.current.createGame('pvp', 'medium') })

    // Inject a white piece at (4, 0) into the game state via WS
    const ws = MockWebSocket.instances[0]
    const stateWithPiece = {
      ...INITIAL_STATE.state,
      board: INITIAL_STATE.state.board.map((row, y) =>
        row.map((cell, x) => ({
          ...cell,
          piece: y === 4 && x === 0 ? { team: 'white', shape: 'square' } : null,
        }))
      ),
    }
    act(() => { ws.emit({ event: 'state_update', state: stateWithPiece }) })

    // Mock the valid-moves fetch
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true, json: () => Promise.resolve({ moves: [[3, 0], [3, 1]] }),
    })

    await act(async () => {
      await hook.result.current.handleCellClick(4, 0)
    })

    expect(hook.result.current.selectedPiece).toEqual([4, 0])
    expect(hook.result.current.validMoves).toEqual([[3, 0], [3, 1]])
  })
})
