/**
 * Tests for the useVoiceControl React hook (frontend/src/useVoiceControl.js).
 *
 * The useVoiceControl hook provides hands-free game control via the Web
 * Speech Recognition API. It parses spoken commands into game actions:
 *   - "skip" / "pass" / "skip moves" → onSkipMoves callback
 *   - "[piece] to [coordinate]" → onVoiceMove(fromPos, toPos)
 *   - "[piece] push [direction]" → onVoicePush(piecePos, directionVector)
 *
 * Piece names are BJJ-themed (sleeve, lapel, belt, neck, joint) and are
 * looked up by scanning the current board state. Coordinates use A-D column
 * letters and 1-10 row numbers.
 *
 * Testing strategy:
 *   - SpeechRecognition is stubbed with MockSpeechRecognition, which provides
 *     an emit() helper to simulate voice recognition results.
 *   - The hook is mounted via renderHook with controlled gameState and
 *     vi.fn() callback spies.
 *   - Tests cover: API support detection (standard + webkit fallback),
 *     toggle on/off, skip/pass commands, move commands with coordinate
 *     parsing, push commands with direction mapping (accounting for board
 *     transposition), error states (piece not found, unrecognized commands),
 *     and microphone permission errors.
 *
 * Important: The board is visually transposed (rows become columns), so
 * direction mapping differs from intuition:
 *   - Visual down → dx+1 → [0, 1]
 *   - Visual up → dx-1 → [0, -1]
 *   - Visual left → dy-1 → [-1, 0]
 *   - Visual right → dy+1 → [1, 0]
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useVoiceControl } from '../useVoiceControl'

// ---------------------------------------------------------------------------
// SpeechRecognition stub
// ---------------------------------------------------------------------------

/**
 * Minimal SpeechRecognition stub for testing voice commands without a
 * real microphone. Tracks the singleton instance and provides emit() to
 * simulate recognition results.
 */
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

  /** Simulate a speech recognition result with the given transcript string. */
  emit(transcript) {
    this.onresult?.({
      results: [[{ transcript }]],
    })
  }
}
MockSpeechRecognition.instance = null

// ---------------------------------------------------------------------------
// Test board helper — 10x4 grid with optional piece overrides
// ---------------------------------------------------------------------------

/** Build a minimal 10x4 board grid with kill zones at rows 0 and 9.
 *  The pieces map uses "y,x" string keys to place specific pieces. */
function makeBoard(pieces = {}) {
  return Array.from({ length: 10 }, (_, y) =>
    Array.from({ length: 4 }, (_, x) => ({
      killZone: y === 0 || y === 9,
      piece: pieces[`${y},${x}`] ?? null,
      isAnchor: false,
    }))
  )
}

/** Build a game state with sensible defaults. Override pieces, currentPlayer,
 *  or any other field via the overrides parameter. */
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

/** Standard piece layout for most voice control tests: 5 white pieces with
 *  BJJ names at known positions. This mirrors the initial game layout. */
const STANDARD_PIECES = {
  '4,0': { team: 'white', shape: 'square', name: 'sleeve' },
  '4,1': { team: 'white', shape: 'square', name: 'lapel'  },
  '4,2': { team: 'white', shape: 'square', name: 'belt'   },
  '4,3': { team: 'white', shape: 'round',  name: 'neck'   },
  '3,1': { team: 'white', shape: 'round',  name: 'joint'  },
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  /** Install the mock SpeechRecognition on window and clear the webkit
   *  fallback so tests start with a clean API surface. */
  window.SpeechRecognition = MockSpeechRecognition
  window.webkitSpeechRecognition = undefined
})

afterEach(() => {
  /** Remove speech recognition mocks and reset state between tests. */
  delete window.SpeechRecognition
  delete window.webkitSpeechRecognition
  MockSpeechRecognition.instance = null
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// Helper to mount the hook with standard defaults
// ---------------------------------------------------------------------------

/**
 * Mount the useVoiceControl hook with the standard piece layout and
 * vi.fn() spies for all callbacks. Accepts overrides for gameState or
 * individual callbacks to test specific scenarios.
 */
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
  /** Tests for browser support detection. The hook must check for both
   *  the standard SpeechRecognition API and the webkit-prefixed fallback
   *  used by Safari and older Chrome versions. */

  it('is true when SpeechRecognition is available', () => {
    /** Standard API available → voice control is supported. */
    const { result } = setup()
    expect(result.current.isSupported).toBe(true)
  })

  it('is false when SpeechRecognition is not available', () => {
    /** Neither standard nor webkit API → voice control is not supported.
     *  The UI should hide the microphone button in this case. */
    delete window.SpeechRecognition
    const { result } = setup()
    expect(result.current.isSupported).toBe(false)
  })

  it('uses webkitSpeechRecognition as fallback', () => {
    /** Safari uses webkitSpeechRecognition — the hook must detect this
     *  as a valid fallback and report isSupported=true. */
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
  /** Tests for the toggle() method that starts/stops voice recognition.
   *  The hook must track isListening state and toggle it on each call. */

  it('starts not listening', () => {
    /** Voice recognition must be off by default — the user must explicitly
     *  opt in by calling toggle(). */
    const { result } = setup()
    expect(result.current.isListening).toBe(false)
  })

  it('sets isListening to true when toggled on', () => {
    /** First toggle call should start listening. */
    const { result } = setup()
    act(() => { result.current.toggle() })
    expect(result.current.isListening).toBe(true)
  })

  it('sets isListening back to false when toggled off', () => {
    /** Second toggle call should stop listening. */
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
  /** Tests for skip/pass voice commands. All three variations ("skip",
   *  "pass", "skip moves") should trigger the onSkipMoves callback,
   *  allowing the player to forgo their optional moves via voice. */

  it('calls onSkipMoves when "skip" is spoken', () => {
    /** The word "skip" alone should trigger onSkipMoves and set lastCommand
     *  status to 'ok'. */
    const { result, onSkipMoves } = setup()
    act(() => { MockSpeechRecognition.instance.emit('skip') })
    expect(onSkipMoves).toHaveBeenCalledTimes(1)
    expect(result.current.lastCommand.status).toBe('ok')
  })

  it('calls onSkipMoves when "pass" is spoken', () => {
    /** "pass" is an alias for "skip" — natural for tabletop game players. */
    const { onSkipMoves } = setup()
    act(() => { MockSpeechRecognition.instance.emit('pass') })
    expect(onSkipMoves).toHaveBeenCalledTimes(1)
  })

  it('calls onSkipMoves when "skip moves" is spoken', () => {
    /** "skip moves" is the most explicit form — should also trigger skip. */
    const { onSkipMoves } = setup()
    act(() => { MockSpeechRecognition.instance.emit('skip moves') })
    expect(onSkipMoves).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------
// Command: move
// ---------------------------------------------------------------------------

describe('useVoiceControl — move command', () => {
  /** Tests for voice-controlled piece movement. The command grammar is:
   *  "[move] <piece_name> to <column><row>" where column is A-D and row
   *  is 1-10. The "move" prefix is optional. The hook must:
   *  1. Find the named piece on the board by scanning currentPlayer's pieces.
   *  2. Parse the coordinate (e.g., "b4" → row index 3, col index 1).
   *  3. Call onVoiceMove([fromY, fromX], [toY, toX]).
   *
   *  Coordinate conversion: row number N → y index = N-1, column letter → x index.
   */

  it('parses "sleeve to b4" and calls onVoiceMove with correct coords', () => {
    /** sleeve is at (4,0). "b4" means column B (x=1), row 4 (y=3).
     *  Expected call: onVoiceMove([4,0], [3,1]). */
    const { onVoiceMove } = setup()
    act(() => { MockSpeechRecognition.instance.emit('sleeve to b4') })
    expect(onVoiceMove).toHaveBeenCalledWith([4, 0], [3, 1])
  })

  it('parses "move lapel to c3"', () => {
    /** "move" prefix is optional but accepted. lapel is at (4,1).
     *  "c3" → column C (x=2), row 3 (y=2). */
    const { onVoiceMove } = setup()
    act(() => { MockSpeechRecognition.instance.emit('move lapel to c3') })
    expect(onVoiceMove).toHaveBeenCalledWith([4, 1], [2, 2])
  })

  it('parses "neck to a5"', () => {
    /** neck is at (4,3). "a5" → column A (x=0), row 5 (y=4). */
    const { onVoiceMove } = setup()
    act(() => { MockSpeechRecognition.instance.emit('neck to a5') })
    expect(onVoiceMove).toHaveBeenCalledWith([4, 3], [4, 0])
  })

  it('sets status to ok on successful parse', () => {
    /** A successfully parsed and dispatched command must set lastCommand
     *  status to 'ok' for UI feedback (e.g., green checkmark). */
    const { result } = setup()
    act(() => { MockSpeechRecognition.instance.emit('sleeve to b4') })
    expect(result.current.lastCommand.status).toBe('ok')
  })

  it('sets status to err when piece is not found on board', () => {
    /** If the named piece doesn't exist on the board (empty board), the
     *  hook must set status='err' with a detail message mentioning the
     *  piece name so the user knows what went wrong. */
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
  /** Tests for voice-controlled push actions. The command grammar is:
   *  "<piece_name> push <direction>" where direction is up/down/left/right.
   *
   *  IMPORTANT: The board is visually transposed (rows render as columns),
   *  so the direction mapping is non-obvious:
   *    - Visual "down" = dx+1 = engine direction [0, 1]
   *    - Visual "up"   = dx-1 = engine direction [0, -1]
   *    - Visual "left"  = dy-1 = engine direction [-1, 0]
   *    - Visual "right" = dy+1 = engine direction [1, 0]
   */

  it('parses "lapel push down" and calls onVoicePush', () => {
    /** lapel at (4,1), visual down → engine [0, 1]. */
    const { onVoicePush } = setup()
    act(() => { MockSpeechRecognition.instance.emit('lapel push down') })
    expect(onVoicePush).toHaveBeenCalledWith([4, 1], [0, 1])
  })

  it('parses "belt push up"', () => {
    /** belt at (4,2), visual up → engine [0, -1]. */
    const { onVoicePush } = setup()
    act(() => { MockSpeechRecognition.instance.emit('belt push up') })
    expect(onVoicePush).toHaveBeenCalledWith([4, 2], [0, -1])
  })

  it('parses "sleeve push left"', () => {
    /** sleeve at (4,0), visual left → engine [-1, 0]. */
    const { onVoicePush } = setup()
    act(() => { MockSpeechRecognition.instance.emit('sleeve push left') })
    expect(onVoicePush).toHaveBeenCalledWith([4, 0], [-1, 0])
  })

  it('parses "sleeve push right"', () => {
    /** sleeve at (4,0), visual right → engine [1, 0]. */
    const { onVoicePush } = setup()
    act(() => { MockSpeechRecognition.instance.emit('sleeve push right') })
    expect(onVoicePush).toHaveBeenCalledWith([4, 0], [1, 0])
  })

  it('sets status to err when piece not found', () => {
    /** If the board is empty, the piece lookup fails and the hook must
     *  report an error with the piece name in the detail. */
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
  /** Tests for unrecognized voice input. When the spoken text doesn't match
   *  any known command grammar, the hook should report 'no-match' status
   *  and NOT invoke any action callbacks. */

  it('sets status to no-match for unrecognised input', () => {
    /** Arbitrary speech that doesn't match move/push/skip patterns must
     *  set status='no-match' with the raw transcript preserved in text. */
    const { result } = setup()
    act(() => { MockSpeechRecognition.instance.emit('do a barrel roll') })
    expect(result.current.lastCommand.status).toBe('no-match')
    expect(result.current.lastCommand.text).toBe('do a barrel roll')
  })

  it('does not call any action callback on no-match', () => {
    /** Unrecognized input must be silently ignored — no game actions should
     *  be triggered to prevent accidental moves from misrecognition. */
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
  /** Tests for handling SpeechRecognition errors, particularly microphone
   *  permission denial. The hook must gracefully stop listening and report
   *  the error so the UI can display a helpful message. */

  it('sets isListening to false on not-allowed error', () => {
    /** When the user denies microphone permission (or the browser blocks it),
     *  SpeechRecognition fires a 'not-allowed' error. The hook must:
     *  1. Set isListening to false (stop trying to listen).
     *  2. Set lastCommand.status to 'err' with a "denied" detail message. */
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
