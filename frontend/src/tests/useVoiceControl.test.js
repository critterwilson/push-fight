import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useVoiceControl } from '../useVoiceControl'

// ---------------------------------------------------------------------------
// SpeechRecognition stub
// ---------------------------------------------------------------------------

class MockSpeechRecognition {
  constructor() {
    this.continuous     = false
    this.interimResults = false
    this.lang           = ''
    this.onresult       = null
    this.onend          = null
    this.onerror        = null
    MockSpeechRecognition.instance = this
  }
  start()  { this.started = true }
  stop()   { this.started = false }
  abort()  { this.started = false }

  /** Helper: simulate a speech recognition result. */
  emit(transcript) {
    this.onresult?.({
      results: [[{ transcript }]],
    })
  }
}
MockSpeechRecognition.instance = null

// ---------------------------------------------------------------------------
// Test board helper — 10×4 grid with one named piece per slot
// ---------------------------------------------------------------------------

function makeBoard(pieces = {}) {
  return Array.from({ length: 10 }, (_, y) =>
    Array.from({ length: 4 }, (_, x) => ({
      killZone: y === 0 || y === 9,
      piece: pieces[`${y},${x}`] ?? null,
      isAnchor: false,
    }))
  )
}

function makeGameState(overrides = {}) {
  return {
    board: makeBoard(overrides.pieces ?? {}),
    currentPlayer: overrides.currentPlayer ?? 'white',
    canMove: true,
    canPush: false,
    gameOver: false,
    ...overrides,
  }
}

// Standard state: white 'sleeve' at (4,0), 'lapel' at (4,1)
const STANDARD_PIECES = {
  '4,0': { team: 'white', shape: 'square', name: 'sleeve' },
  '4,1': { team: 'white', shape: 'square', name: 'lapel'  },
  '4,2': { team: 'white', shape: 'square', name: 'belt'   },
  '4,3': { team: 'white', shape: 'round',  name: 'choke'  },
  '3,1': { team: 'white', shape: 'round',  name: 'lock'   },
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  window.SpeechRecognition = MockSpeechRecognition
  window.webkitSpeechRecognition = undefined
})

afterEach(() => {
  delete window.SpeechRecognition
  delete window.webkitSpeechRecognition
  MockSpeechRecognition.instance = null
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// Helper to mount the hook with standard defaults
// ---------------------------------------------------------------------------

function setup(overrides = {}) {
  const onVoiceMove  = vi.fn()
  const onVoicePush  = vi.fn()
  const onSkipMoves  = vi.fn()
  const gameState    = makeGameState({ pieces: STANDARD_PIECES })

  const { result } = renderHook(() =>
    useVoiceControl({
      gameState:   overrides.gameState   ?? gameState,
      sessionId:   'test-session',
      onVoiceMove: overrides.onVoiceMove ?? onVoiceMove,
      onVoicePush: overrides.onVoicePush ?? onVoicePush,
      onSkipMoves: overrides.onSkipMoves ?? onSkipMoves,
    })
  )

  return { result, onVoiceMove, onVoicePush, onSkipMoves }
}

// ---------------------------------------------------------------------------
// isSupported
// ---------------------------------------------------------------------------

describe('useVoiceControl — isSupported', () => {
  it('is true when SpeechRecognition is available', () => {
    const { result } = setup()
    expect(result.current.isSupported).toBe(true)
  })

  it('is false when SpeechRecognition is not available', () => {
    delete window.SpeechRecognition
    const { result } = setup()
    expect(result.current.isSupported).toBe(false)
  })

  it('uses webkitSpeechRecognition as fallback', () => {
    delete window.SpeechRecognition
    window.webkitSpeechRecognition = MockSpeechRecognition
    const { result } = setup()
    expect(result.current.isSupported).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// toggle
// ---------------------------------------------------------------------------

describe('useVoiceControl — toggle', () => {
  it('starts not listening', () => {
    const { result } = setup()
    expect(result.current.isListening).toBe(false)
  })

  it('sets isListening to true when toggled on', () => {
    const { result } = setup()
    act(() => { result.current.toggle() })
    expect(result.current.isListening).toBe(true)
  })

  it('sets isListening back to false when toggled off', () => {
    const { result } = setup()
    act(() => { result.current.toggle() }) // on
    act(() => { result.current.toggle() }) // off
    expect(result.current.isListening).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Command: skip / pass
// ---------------------------------------------------------------------------

describe('useVoiceControl — skip command', () => {
  it('calls onSkipMoves when "skip" is spoken', () => {
    const { result, onSkipMoves } = setup()
    act(() => { MockSpeechRecognition.instance.emit('skip') })
    expect(onSkipMoves).toHaveBeenCalledTimes(1)
    expect(result.current.lastCommand.status).toBe('ok')
  })

  it('calls onSkipMoves when "pass" is spoken', () => {
    const { onSkipMoves } = setup()
    act(() => { MockSpeechRecognition.instance.emit('pass') })
    expect(onSkipMoves).toHaveBeenCalledTimes(1)
  })

  it('calls onSkipMoves when "skip moves" is spoken', () => {
    const { onSkipMoves } = setup()
    act(() => { MockSpeechRecognition.instance.emit('skip moves') })
    expect(onSkipMoves).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------
// Command: move
// ---------------------------------------------------------------------------

describe('useVoiceControl — move command', () => {
  it('parses "sleeve to b4" and calls onVoiceMove with correct coords', () => {
    const { onVoiceMove } = setup()
    act(() => { MockSpeechRecognition.instance.emit('sleeve to b4') })
    // from = [4,0] (where sleeve is), to = [3, 1] (row 4 → index 3, col b → index 1)
    expect(onVoiceMove).toHaveBeenCalledWith([4, 0], [3, 1])
  })

  it('parses "move lapel to c3"', () => {
    const { onVoiceMove } = setup()
    act(() => { MockSpeechRecognition.instance.emit('move lapel to c3') })
    expect(onVoiceMove).toHaveBeenCalledWith([4, 1], [2, 2])
  })

  it('parses "choke to a5"', () => {
    const { onVoiceMove } = setup()
    act(() => { MockSpeechRecognition.instance.emit('choke to a5') })
    expect(onVoiceMove).toHaveBeenCalledWith([4, 3], [4, 0])
  })

  it('sets status to ok on successful parse', () => {
    const { result } = setup()
    act(() => { MockSpeechRecognition.instance.emit('sleeve to b4') })
    expect(result.current.lastCommand.status).toBe('ok')
  })

  it('sets status to err when piece is not found on board', () => {
    const emptyState = makeGameState({ pieces: {} })
    const { result } = setup({ gameState: emptyState })
    act(() => { MockSpeechRecognition.instance.emit('sleeve to b4') })
    expect(result.current.lastCommand.status).toBe('err')
    expect(result.current.lastCommand.detail).toMatch(/sleeve/i)
  })
})

// ---------------------------------------------------------------------------
// Command: push
// ---------------------------------------------------------------------------

describe('useVoiceControl — push command', () => {
  it('parses "lapel push down" and calls onVoicePush', () => {
    const { onVoicePush } = setup()
    act(() => { MockSpeechRecognition.instance.emit('lapel push down') })
    expect(onVoicePush).toHaveBeenCalledWith([4, 1], [1, 0])
  })

  it('parses "belt push up"', () => {
    const { onVoicePush } = setup()
    act(() => { MockSpeechRecognition.instance.emit('belt push up') })
    expect(onVoicePush).toHaveBeenCalledWith([4, 2], [-1, 0])
  })

  it('parses "sleeve push left"', () => {
    const { onVoicePush } = setup()
    act(() => { MockSpeechRecognition.instance.emit('sleeve push left') })
    expect(onVoicePush).toHaveBeenCalledWith([4, 0], [0, -1])
  })

  it('parses "sleeve push right"', () => {
    const { onVoicePush } = setup()
    act(() => { MockSpeechRecognition.instance.emit('sleeve push right') })
    expect(onVoicePush).toHaveBeenCalledWith([4, 0], [0, 1])
  })

  it('sets status to err when piece not found', () => {
    const emptyState = makeGameState({ pieces: {} })
    const { result } = setup({ gameState: emptyState })
    act(() => { MockSpeechRecognition.instance.emit('sleeve push down') })
    expect(result.current.lastCommand.status).toBe('err')
    expect(result.current.lastCommand.detail).toMatch(/sleeve/i)
  })
})

// ---------------------------------------------------------------------------
// Command: no-match
// ---------------------------------------------------------------------------

describe('useVoiceControl — no-match', () => {
  it('sets status to no-match for unrecognised input', () => {
    const { result } = setup()
    act(() => { MockSpeechRecognition.instance.emit('do a barrel roll') })
    expect(result.current.lastCommand.status).toBe('no-match')
    expect(result.current.lastCommand.text).toBe('do a barrel roll')
  })

  it('does not call any action callback on no-match', () => {
    const { onVoiceMove, onVoicePush, onSkipMoves } = setup()
    act(() => { MockSpeechRecognition.instance.emit('hello world') })
    expect(onVoiceMove).not.toHaveBeenCalled()
    expect(onVoicePush).not.toHaveBeenCalled()
    expect(onSkipMoves).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

describe('useVoiceControl — microphone error', () => {
  it('sets isListening to false on not-allowed error', () => {
    const { result } = setup()
    act(() => { result.current.toggle() }) // start listening
    expect(result.current.isListening).toBe(true)

    act(() => {
      MockSpeechRecognition.instance.onerror?.({ error: 'not-allowed' })
    })

    expect(result.current.isListening).toBe(false)
    expect(result.current.lastCommand.status).toBe('err')
    expect(result.current.lastCommand.detail).toMatch(/denied/i)
  })
})
