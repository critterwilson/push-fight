import { useState, useEffect, useRef, useCallback } from 'react'
import * as api from './api'

// ---------------------------------------------------------------------------
// WebSocket connection helper — held in a ref so reconnect closures are fresh
// ---------------------------------------------------------------------------

function makeConnector({ sessionId, onMessage, onStatusChange, onError }) {
  const wsRef      = { current: null }
  const timerRef   = { current: null }
  const destroyed  = { current: false }

  function connect() {
    if (destroyed.current) return
    clearTimeout(timerRef.current)

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws    = new WebSocket(`${proto}://${window.location.host}/ws/${sessionId}`)
    wsRef.current = ws

    ws.onopen    = () => onStatusChange('connected')
    ws.onmessage = ({ data }) => onMessage(JSON.parse(data))

    ws.onclose = (event) => {
      onStatusChange('disconnected')
      if (event.code === 4004) {
        // Server closed the session — don't reconnect, tell the user
        onError('Session expired. Please start a new game.')
        return
      }
      // Attempt reconnect after 2 s
      timerRef.current = setTimeout(connect, 2000)
    }

    ws.onerror = () => {} // onclose fires after onerror, handles everything
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
  const [sessionId, setSessionId]         = useState(null)
  const [gameState, setGameState]         = useState(null)
  const [selectedPiece, setSelectedPiece] = useState(null)  // [y, x] | null
  const [validMoves, setValidMoves]       = useState([])    // [[y, x], …]
  const [validPushDirs, setValidPushDirs] = useState([])    // [[dy, dx], …]
  const [aiThinking, setAiThinking]       = useState(false)
  const [pendingAiAction, setPendingAiAction] = useState(null) // action dict while AI animates
  const [messages, setMessages]           = useState([])
  const [error, setError]                 = useState(null)
  const [connectionStatus, setConnectionStatus] = useState('idle') // 'idle'|'connected'|'disconnected'

  const errorTimerRef = useRef(null)
  const connectorRef  = useRef(null)

  // ── helpers ───────────────────────────────────────────────────────────────

  const deselect = useCallback(() => {
    setSelectedPiece(null)
    setValidMoves([])
    setValidPushDirs([])
  }, [])

  const showError = useCallback((msg) => {
    setError(msg)
    clearTimeout(errorTimerRef.current)
    errorTimerRef.current = setTimeout(() => setError(null), 3500)
  }, [])

  // ── WebSocket lifecycle ───────────────────────────────────────────────────

  useEffect(() => {
    if (!sessionId) return

    const connector = makeConnector({
      sessionId,
      onStatusChange: setConnectionStatus,
      onError: showError,
      onMessage(msg) {
        switch (msg.event) {
          case 'state_update':
            setGameState(msg.state)
            setPendingAiAction(null)
            setSelectedPiece(null)
            setValidMoves([])
            setValidPushDirs([])
            break
          case 'ai_action':
            setAiThinking(true)
            setPendingAiAction(msg.action)  // lets Board highlight the moving piece
            break
          case 'ai_done':
            setAiThinking(false)
            setPendingAiAction(null)
            break
          case 'rag_answer':
            setMessages(prev => {
              // Replace the last loading placeholder with the real answer
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

    return () => connector.destroy()
  }, [sessionId, showError])

  // ── Game actions ──────────────────────────────────────────────────────────

  const createGame = useCallback(async (mode, difficulty) => {
    try {
      const data = await api.createGame(mode, difficulty)
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

  const handleCellClick = useCallback(async (y, x) => {
    if (!sessionId || !gameState) return
    if (gameState.gameOver || gameState.isAiTurn) return

    const piece = gameState.board[y][x].piece

    // ── Move phase ──────────────────────────────────────────────────────────
    if (gameState.canMove) {
      // Execute pending move if destination is valid
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

      // Select / deselect own piece
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

    // ── Push phase ───────────────────────────────────────────────────────────
    if (gameState.canPush) {
      if (selectedPiece?.[0] === y && selectedPiece?.[1] === x) {
        deselect()
        return
      }

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

  const askReferee = useCallback(async (question) => {
    if (!sessionId || !question.trim()) return
    setMessages(prev => [
      ...prev,
      { from: 'user', text: question },
      { from: 'referee', text: 'Thinking…', loading: true },
    ])
    try {
      await api.askReferee(sessionId, question)
    } catch (e) {
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

  // Direct action callers used by voice control (bypass click-state machine)
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

  const saveGame = useCallback(async (filename) => {
    if (!sessionId) return
    try {
      await api.saveGame(sessionId, filename)
    } catch (e) {
      showError(e.message)
    }
  }, [sessionId, showError])

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
  }
}
