/**
 * useVoiceControl — Web Speech API integration for hands-free gameplay.
 *
 * Recognizes three types of spoken commands:
 *
 *   1. **Skip**: "skip" or "pass" — skips remaining moves.
 *   2. **Move**: "<piece> to <col><row>" — e.g. "sleeve to B4".
 *      Looks up the piece by name on the current player's team and
 *      slides it to the specified cell.
 *   3. **Push**: "<piece> push <direction>" — e.g. "lapel push down".
 *      Pushes with the named square piece in the spoken direction.
 *
 * Piece names: sleeve, lapel, belt, neck, joint (BJJ theme).
 * Column letters: A–D (mapped to indices 0–3).
 * Directions: up, down, left, right (mapped to board-transposed vectors).
 *
 * The hook uses refs to keep closures fresh inside the SpeechRecognition
 * callbacks, since the recognition instance is created once and persists
 * across re-renders.  The recognition is set to non-continuous mode and
 * auto-restarts after each result to keep state clean.
 *
 * Returns: { isListening, isSupported, lastCommand, toggle }
 */

import { useState, useEffect, useRef, useCallback } from 'react'

/** Grammar definitions for matching spoken commands. */
const GRAMMAR = {
  pieces: ['sleeve', 'lapel', 'belt', 'neck', 'joint'],
  dirs:   ['up', 'down', 'left', 'right'],
  cols:   { a: 0, b: 1, c: 2, d: 3 },
}

export function useVoiceControl({ gameState, sessionId, onVoiceMove, onVoicePush, onSkipMoves }) {
  const [isListening, setIsListening] = useState(false)
  const [lastCommand, setLastCommand] = useState(null) // { text, status: 'ok'|'err'|'no-match', detail? }
  const [isSupported, setIsSupported] = useState(false)

  // Refs keep callbacks and game state fresh inside the long-lived
  // SpeechRecognition event handlers (avoids stale closures)
  const stateRef = useRef({ gameState, onVoiceMove, onVoicePush, onSkipMoves })
  useEffect(() => {
    stateRef.current = { gameState, onVoiceMove, onVoicePush, onSkipMoves }
  }, [gameState, onVoiceMove, onVoicePush, onSkipMoves])

  const recognitionRef = useRef(null)
  const isListeningRef = useRef(isListening)

  useEffect(() => {
    isListeningRef.current = isListening
  }, [isListening])

  // ── Initialize SpeechRecognition (once on mount) ──────────────────────

  useEffect(() => {
    if (typeof window === 'undefined') return

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SpeechRecognition) {
      setIsSupported(true)
      const recognition = new SpeechRecognition()
      recognition.continuous = false  // Restart manually to keep state clean
      recognition.interimResults = false
      recognition.lang = 'en-US'
      recognitionRef.current = recognition

      // Process each recognized phrase
      recognition.onresult = (event) => {
        const text = event.results[0][0].transcript.toLowerCase().trim()
        processCommand(text)
      }

      // Auto-restart if we should still be listening (non-continuous mode
      // fires onend after each recognition result)
      recognition.onend = () => {
        if (isListeningRef.current) {
          try {
            recognition.start()
          } catch (e) {
            // Ignore — may fire if already started
          }
        }
      }

      // Handle permission denial
      recognition.onerror = (event) => {
        if (event.error === 'not-allowed') {
          setIsListening(false)
          setLastCommand({ text: '', status: 'err', detail: 'Microphone access denied' })
        }
      }
    }

    return () => {
      if (recognitionRef.current) recognitionRef.current.abort()
    }
  }, [])

  // ── Toggle listening on/off ───────────────────────────────────────────

  const toggle = useCallback(() => {
    if (!recognitionRef.current) return

    if (isListening) {
      setIsListening(false)
      recognitionRef.current.stop()
    } else {
      setIsListening(true)
      try {
        recognitionRef.current.start()
      } catch (e) {
        console.error(e)
      }
    }
  }, [isListening])

  // ── Command parser ────────────────────────────────────────────────────

  /**
   * Parse a spoken text string into a game action.
   *
   * Matching priority:
   *   1. "skip" / "pass" → skip moves
   *   2. "<piece> to <col><row>" → move command
   *   3. "<piece> push <direction>" → push command
   *   4. No match → feedback toast
   */
  const processCommand = (text) => {
    const { gameState, onVoiceMove, onVoicePush, onSkipMoves } = stateRef.current

    // 1. Skip / pass command
    if (text.includes('skip') || text.includes('pass')) {
      onSkipMoves()
      setLastCommand({ text, status: 'ok' })
      return
    }

    /**
     * Find a named piece on the current player's team.
     * Scans the entire 10×4 board for a matching piece.
     * Returns [y, x] or null.
     */
    const findPiece = (name) => {
      const team = gameState.currentPlayer
      for (let y = 0; y < 10; y++) {
        for (let x = 0; x < 4; x++) {
          const p = gameState.board[y][x].piece
          if (p && p.team === team && p.name === name) return [y, x]
        }
      }
      return null
    }

    // 2. Move command: "sleeve to b4"
    const moveMatch = text.match(new RegExp(`(${GRAMMAR.pieces.join('|')}).*?([a-d])\\s*([0-9]+)`, 'i'))
    if (moveMatch) {
      const [_, pieceName, colStr, rowStr] = moveMatch
      const fromPos = findPiece(pieceName)

      if (!fromPos) {
        setLastCommand({ text, status: 'err', detail: `${pieceName} not found` })
        return
      }

      const toCol = GRAMMAR.cols[colStr]
      const toRow = parseInt(rowStr, 10) - 1  // Convert 1-indexed to 0-indexed

      if (toRow < 0 || toRow > 9) {
        setLastCommand({ text, status: 'err', detail: 'Invalid row' })
        return
      }

      onVoiceMove(fromPos, [toRow, toCol])
      setLastCommand({ text, status: 'ok' })
      return
    }

    // 3. Push command: "lapel push down"
    const pushMatch = text.match(new RegExp(`(${GRAMMAR.pieces.join('|')}).*?push\\s+(${GRAMMAR.dirs.join('|')})`, 'i'))
    if (pushMatch) {
      const [_, pieceName, dirStr] = pushMatch
      const pos = findPiece(pieceName)

      if (!pos) {
        setLastCommand({ text, status: 'err', detail: `${pieceName} not found` })
        return
      }

      // Direction mapping accounts for board transposition:
      // Visual right → dy=+1, visual left → dy=-1
      // Visual down  → dx=+1, visual up   → dx=-1
      const dirMap = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] }
      onVoicePush(pos, dirMap[dirStr])
      setLastCommand({ text, status: 'ok' })
      return
    }

    // No pattern matched
    setLastCommand({ text, status: 'no-match' })
  }

  return { isListening, isSupported, lastCommand, toggle }
}
