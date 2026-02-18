import { useState, useEffect, useRef, useCallback } from 'react'

const GRAMMAR = {
  pieces: ['sleeve', 'lapel', 'belt', 'choke', 'lock'],
  dirs:   ['up', 'down', 'left', 'right'],
  cols:   { a: 0, b: 1, c: 2, d: 3 },
}

export function useVoiceControl({ gameState, sessionId, onVoiceMove, onVoicePush, onSkipMoves }) {
  const [isListening, setIsListening] = useState(false)
  const [lastCommand, setLastCommand] = useState(null) // { text, status: 'ok'|'err'|'no-match', detail? }
  const [isSupported, setIsSupported] = useState(false)

  // Refs to keep closures fresh inside the recognition callbacks
  const stateRef = useRef({ gameState, onVoiceMove, onVoicePush, onSkipMoves })
  useEffect(() => {
    stateRef.current = { gameState, onVoiceMove, onVoicePush, onSkipMoves }
  }, [gameState, onVoiceMove, onVoicePush, onSkipMoves])

  const recognitionRef = useRef(null)
  const isListeningRef = useRef(isListening)

  useEffect(() => {
    isListeningRef.current = isListening
  }, [isListening])

  useEffect(() => {
    if (typeof window === 'undefined') return

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SpeechRecognition) {
      setIsSupported(true)
      const recognition = new SpeechRecognition()
      recognition.continuous = false // We restart manually to keep state clean
      recognition.interimResults = false
      recognition.lang = 'en-US'
      recognitionRef.current = recognition

      recognition.onresult = (event) => {
        const text = event.results[0][0].transcript.toLowerCase().trim()
        processCommand(text)
      }

      recognition.onend = () => {
        // Auto-restart if we are supposed to be listening
        if (isListeningRef.current) {
          try {
            recognition.start()
          } catch (e) {
            // ignore errors (e.g. if already started)
          }
        }
      }

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

  const processCommand = (text) => {
    const { gameState, onVoiceMove, onVoicePush, onSkipMoves } = stateRef.current
    
    // 1. Skip
    if (text.includes('skip') || text.includes('pass')) {
      onSkipMoves()
      setLastCommand({ text, status: 'ok' })
      return
    }

    // Helper to find piece position
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

    // 2. Move: "sleeve to b4"
    const moveMatch = text.match(new RegExp(`(${GRAMMAR.pieces.join('|')}).*?([a-d])\\s*([0-9]+)`, 'i'))
    if (moveMatch) {
      const [_, pieceName, colStr, rowStr] = moveMatch
      const fromPos = findPiece(pieceName)
      
      if (!fromPos) {
        setLastCommand({ text, status: 'err', detail: `${pieceName} not found` })
        return
      }

      const toCol = GRAMMAR.cols[colStr]
      const toRow = parseInt(rowStr, 10) - 1

      if (toRow < 0 || toRow > 9) {
        setLastCommand({ text, status: 'err', detail: 'Invalid row' })
        return
      }

      onVoiceMove(fromPos, [toRow, toCol])
      setLastCommand({ text, status: 'ok' })
      return
    }

    // 3. Push: "lapel push down"
    const pushMatch = text.match(new RegExp(`(${GRAMMAR.pieces.join('|')}).*?push\\s+(${GRAMMAR.dirs.join('|')})`, 'i'))
    if (pushMatch) {
      const [_, pieceName, dirStr] = pushMatch
      const pos = findPiece(pieceName)

      if (!pos) {
        setLastCommand({ text, status: 'err', detail: `${pieceName} not found` })
        return
      }

      const dirMap = { up: [-1, 0], down: [1, 0], left: [0, -1], right: [0, 1] }
      onVoicePush(pos, dirMap[dirStr])
      setLastCommand({ text, status: 'ok' })
      return
    }

    setLastCommand({ text, status: 'no-match' })
  }

  return { isListening, isSupported, lastCommand, toggle }
}