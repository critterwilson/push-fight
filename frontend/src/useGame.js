/**
 * useGame — Central game state hook for Push Fight.
 *
 * This hook owns all client-side game state and exposes a complete API
 * for the UI layer:
 *
 *   State:
 *     sessionId, gameState, selectedPiece, validMoves, validPushDirs,
 *     aiThinking, pendingAiAction, messages (chat), error, connectionStatus,
 *     selectedSetupPiece
 *
 *   Actions:
 *     createGame, handleCellClick, handlePushDir, skipMoves,
 *     askReferee, saveGame, loadSave, voiceMove, voicePush,
 *     handleSetupCellClick, confirmSetup, setSelectedSetupPiece
 *
 * Architecture:
 *   - REST calls (via api.js) are used for state-mutating actions.
 *   - A WebSocket connection receives push-based updates (state changes,
 *     AI actions, RAG answers) and keeps the UI in sync.
 *   - The WebSocket auto-reconnects on disconnect (2s delay) and handles
 *     session expiry (code 4004) by showing an error.
 *
 * The cell-click handler implements a two-phase state machine:
 *   1. Move phase: select a piece → see valid moves → click destination.
 *   2. Push phase: select a square piece → see push arrows → click direction.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import * as api from './api'

// ---------------------------------------------------------------------------
// WebSocket connection helper
// ---------------------------------------------------------------------------

/**
 * Creates a WebSocket connector with auto-reconnect.
 *
 * Returns { connect, destroy } functions.  The connector handles:
 *   - Protocol selection (ws: vs wss: based on page protocol)
 *   - Status callbacks (connected / disconnected)
 *   - JSON message parsing and dispatch
 *   - Auto-reconnect after 2 seconds on unexpected close
 *   - Session expiry detection (close code 4004 = no reconnect)
 */
function makeConnector({ sessionId, onMessage, onStatusChange, onError }) {
  const wsRef      = { current: null }
  const timerRef   = { current: null }
  const destroyed  = { current: false }

  function connect() {
    if (destroyed.current) return
    clearTimeout(timerRef.current)

    // Match the page's protocol (http → ws, https → wss)
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws    = new WebSocket(`${proto}://${window.location.host}/ws/${sessionId}`)
    wsRef.current = ws

    ws.onopen    = () => onStatusChange('connected')
    ws.onmessage = ({ data }) => onMessage(JSON.parse(data))

    ws.onclose = (event) => {
      onStatusChange('disconnected')
      if (event.code === 4004) {
        // Server closed the session — don't reconnect
        onError('Session expired. Please start a new game.')
        return
      }
      // Auto-reconnect after 2 seconds
      timerRef.current = setTimeout(connect, 2000)
    }

    // onerror is always followed by onclose, which handles everything
    ws.onerror = () => {}
  }

  function destroy() {
    destroyed.current = true
    clearTimeout(timerRef.current)
    wsRef.current?.close()
  }

  return { connect, destroy }
}

// ---------------------------------------------------------------------------
// useGame hook
// ---------------------------------------------------------------------------

export function useGame() {
  // ── Core game state ───────────────────────────────────────────────────
  const [sessionId, setSessionId]         = useState(null)
  const [gameState, setGameState]         = useState(null)
  const [selectedPiece, setSelectedPiece] = useState(null)  // [y, x] or null
  const [validMoves, setValidMoves]       = useState([])    // [[y, x], ...]
  const [validPushDirs, setValidPushDirs] = useState([])    // [[dy, dx], ...]

  // ── AI state ──────────────────────────────────────────────────────────
  const [aiThinking, setAiThinking]       = useState(false)
  const [pendingAiAction, setPendingAiAction] = useState(null)

  // ── Chat / RAG state ──────────────────────────────────────────────────
  const [messages, setMessages]           = useState([])

  // ── UI state ──────────────────────────────────────────────────────────
  const [error, setError]                 = useState(null)
  const [connectionStatus, setConnectionStatus] = useState('idle')
  const [selectedSetupPiece, setSelectedSetupPiece] = useState(null)

  const errorTimerRef = useRef(null)
  const connectorRef  = useRef(null)

  // ── Helpers ───────────────────────────────────────────────────────────

  /** Clear piece selection and associated valid-action overlays. */
  const deselect = useCallback(() => {
    setSelectedPiece(null)
    setValidMoves([])
    setValidPushDirs([])
  }, [])

  /** Show an error toast that auto-dismisses after 3.5 seconds. */
  const showError = useCallback((msg) => {
    setError(msg)
    clearTimeout(errorTimerRef.current)
    errorTimerRef.current = setTimeout(() => setError(null), 3500)
  }, [])

  // ── WebSocket lifecycle ───────────────────────────────────────────────

  useEffect(() => {
    if (!sessionId) return

    const connector = makeConnector({
      sessionId,
      onStatusChange: setConnectionStatus,
      onError: showError,
      onMessage(msg) {
        switch (msg.event) {
          case 'state_update':
            // Full state refresh — clear all selection state
            setGameState(msg.state)
            setPendingAiAction(null)
            setSelectedPiece(null)
            setValidMoves([])
            setValidPushDirs([])
            break

          case 'ai_action':
            // AI is about to act — highlight the involved piece
            setAiThinking(true)
            setPendingAiAction(msg.action)
            break

          case 'ai_done':
            // AI turn complete — clear thinking state
            setAiThinking(false)
            setPendingAiAction(null)
            break

          case 'rag_answer':
            // Replace the loading placeholder with the real answer
            setMessages(prev => {
              const idx = [...prev].reverse().findIndex(m => m.loading)
              if (idx < 0) return [...prev, { from: 'referee', text: msg.answer }]
              const realIdx = prev.length - 1 - idx
              const next = [...prev]
              next[realIdx] = { from: 'referee', text: msg.answer }
              return next
            })
            break

          case 'error':
            showError(msg.message)
            break
        }
      },
    })

    connectorRef.current = connector
    connector.connect()

    // Clean up WebSocket on unmount or session change
    return () => connector.destroy()
  }, [sessionId, showError])

  // ── Game actions ──────────────────────────────────────────────────────

  /** Create a new game session and reset all local state. */
  const createGame = useCallback(async (mode, difficulty, playerColor = 'white') => {
    try {
      const data = await api.createGame(mode, difficulty, playerColor)
      setSessionId(data.sessionId)
      setGameState(data.state)
      deselect()
      setMessages([])
      setAiThinking(false)
      setPendingAiAction(null)
    } catch (e) {
      showError(e.message)
    }
  }, [deselect, showError])

  /**
   * Board cell click handler — implements the two-phase state machine.
   *
   * Move phase:
   *   - Click own piece → select it, fetch valid moves.
   *   - Click valid destination → execute move.
   *   - Click elsewhere → deselect.
   *
   * Push phase:
   *   - Click own square piece → select it, fetch valid push directions.
   *   - Click same piece again → deselect.
   *   - Push direction arrows handle the actual push (via handlePushDir).
   */
  const handleCellClick = useCallback(async (y, x) => {
    if (!sessionId || !gameState) return
    if (gameState.gameOver || gameState.isAiTurn) return

    const piece = gameState.board[y][x].piece

    // ── Move phase ──────────────────────────────────────────────────────
    if (gameState.canMove) {
      // Try to execute a pending move to this destination
      if (selectedPiece) {
        const isValid = validMoves.some(([my, mx]) => my === y && mx === x)
        if (isValid) {
          try {
            const data = await api.makeMove(sessionId, selectedPiece, [y, x])
            setGameState(data.state)
            deselect()
          } catch (e) {
            showError(e.message)
          }
          return
        }
      }

      // Select or deselect an own piece
      if (piece?.team === gameState.currentPlayer) {
        if (selectedPiece?.[0] === y && selectedPiece?.[1] === x) {
          deselect()
        } else {
          setSelectedPiece([y, x])
          setValidPushDirs([])
          try {
            const data = await api.getValidMoves(sessionId, y, x)
            setValidMoves(data.moves)
          } catch (e) {
            showError(e.message)
          }
        }
        return
      }

      deselect()
      return
    }

    // ── Push phase ──────────────────────────────────────────────────────
    if (gameState.canPush) {
      // Toggle selection on same piece
      if (selectedPiece?.[0] === y && selectedPiece?.[1] === x) {
        deselect()
        return
      }

      // Select a square piece for pushing
      if (piece?.team === gameState.currentPlayer && piece.shape === 'square') {
        setSelectedPiece([y, x])
        setValidMoves([])
        try {
          const data = await api.getValidPushes(sessionId, y, x)
          setValidPushDirs(data.directions)
        } catch (e) {
          showError(e.message)
        }
        return
      }

      deselect()
    }
  }, [sessionId, gameState, selectedPiece, validMoves, deselect, showError])

  /** Execute a push in the given direction with the currently selected piece. */
  const handlePushDir = useCallback(async (dy, dx) => {
    if (!sessionId || !selectedPiece) return
    try {
      const data = await api.makePush(sessionId, selectedPiece, [dy, dx])
      setGameState(data.state)
      deselect()
    } catch (e) {
      showError(e.message)
    }
  }, [sessionId, selectedPiece, deselect, showError])

  /** Skip remaining moves and advance to the push phase. */
  const skipMoves = useCallback(async () => {
    if (!sessionId) return
    try {
      const data = await api.skipMoves(sessionId)
      setGameState(data.state)
      deselect()
    } catch (e) {
      showError(e.message)
    }
  }, [sessionId, deselect, showError])

  /** Submit a question to the RAG referee. Shows a loading placeholder. */
  const askReferee = useCallback(async (question) => {
    if (!sessionId || !question.trim()) return
    // Add user message + loading placeholder immediately for responsiveness
    setMessages(prev => [
      ...prev,
      { from: 'user', text: question },
      { from: 'referee', text: 'Thinking…', loading: true },
    ])
    try {
      await api.askReferee(sessionId, question)
    } catch (e) {
      // Replace loading placeholder with error message
      setMessages(prev => {
        const idx = [...prev].reverse().findIndex(m => m.loading)
        if (idx < 0) return prev
        const realIdx = prev.length - 1 - idx
        const next = [...prev]
        next[realIdx] = { from: 'referee', text: `Error: ${e.message}` }
        return next
      })
    }
  }, [sessionId])

  // ── Voice control actions (bypass click-state machine) ────────────────

  /** Execute a move directly (used by voice control). */
  const voiceMove = useCallback(async (from, to) => {
    if (!sessionId) return
    try {
      const data = await api.makeMove(sessionId, from, to)
      setGameState(data.state)
      deselect()
    } catch (e) {
      showError(e.message)
    }
  }, [sessionId, deselect, showError])

  /** Execute a push directly (used by voice control). */
  const voicePush = useCallback(async (pos, dir) => {
    if (!sessionId) return
    try {
      const data = await api.makePush(sessionId, pos, dir)
      setGameState(data.state)
      deselect()
    } catch (e) {
      showError(e.message)
    }
  }, [sessionId, deselect, showError])

  // ── Setup phase ───────────────────────────────────────────────────────

  /**
   * Setup-phase cell click handler.
   *
   * - Click a placed piece belonging to current player → remove it.
   * - Click an empty valid cell with a piece selected → place it.
   * - Auto-clears the setup piece selection when all pieces are placed.
   */
  const handleSetupCellClick = useCallback(async (y, x) => {
    if (!sessionId || !gameState?.setupMode) return
    const cell = gameState.board[y][x]
    const piece = cell.piece

    // Remove a placed piece (click on own piece = undo)
    if (piece?.team === gameState.currentPlayer) {
      try {
        const data = await api.setupRemove(sessionId, y, x)
        setGameState(data.state)
      } catch (e) {
        showError(e.message)
      }
      return
    }

    // Place the selected piece on an empty, non-kill-zone cell
    if (selectedSetupPiece && !piece && !cell.killZone) {
      try {
        const data = await api.setupPlace(sessionId, y, x, selectedSetupPiece)
        setGameState(data.state)
        // Auto-clear selection once all pieces are placed
        const team = gameState.currentPlayer
        const afterUnplaced = data.state.placementStatus[team].unplaced
        if (afterUnplaced.length === 0) setSelectedSetupPiece(null)
      } catch (e) {
        showError(e.message)
      }
    }
  }, [sessionId, gameState, selectedSetupPiece, showError])

  /** Confirm the current team's piece placement and advance setup. */
  const confirmSetup = useCallback(async () => {
    if (!sessionId) return
    try {
      const data = await api.setupConfirm(sessionId)
      setGameState(data.state)
      setSelectedSetupPiece(null)
    } catch (e) {
      showError(e.message)
    }
  }, [sessionId, showError])

  /** Save the current game state to a named file on the server. */
  const saveGame = useCallback(async (filename) => {
    if (!sessionId) return
    try {
      await api.saveGame(sessionId, filename)
    } catch (e) {
      showError(e.message)
    }
  }, [sessionId, showError])

  /** Load a saved game into the current session. */
  const loadSave = useCallback(async (filename) => {
    if (!sessionId) return
    try {
      const data = await api.loadSave(sessionId, filename)
      setGameState(data.state)
      deselect()
    } catch (e) {
      showError(e.message)
    }
  }, [sessionId, deselect, showError])

  // ── Public API ────────────────────────────────────────────────────────

  return {
    sessionId,
    gameState,
    selectedPiece,
    validMoves,
    validPushDirs,
    aiThinking,
    pendingAiAction,
    messages,
    error,
    connectionStatus,
    createGame,
    handleCellClick,
    handlePushDir,
    skipMoves,
    askReferee,
    saveGame,
    loadSave,
    voiceMove,
    voicePush,
    selectedSetupPiece,
    setSelectedSetupPiece,
    handleSetupCellClick,
    confirmSetup,
  }
}
