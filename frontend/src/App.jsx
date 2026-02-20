/**
 * App — Root component for Push Fight: BJJ Edition.
 *
 * Composes the full application layout:
 *   - Header with title, connection status, theme toggle, voice control,
 *     referee chat toggle, and "How to Play" tutorial.
 *   - Main game area with the SVG board and side panel (status bar,
 *     game controls, optional chat panel).
 *   - New Game modal (shown on first load and on demand).
 *   - Tutorial modal explaining the rules.
 *   - Footer with the Unicorn Delivery Service mascot.
 *
 * State management is delegated to the useGame() hook, which handles
 * all API calls, WebSocket communication, and game state updates.
 * Voice control is handled by the useVoiceControl() hook, which
 * integrates the Web Speech API with the game actions.
 */

import { useState } from 'react'
import ThemeToggle from './ThemeToggle'
import { useGame } from './useGame'
import { useVoiceControl } from './useVoiceControl'
import { Board } from './Board'
import { StatusBar } from './StatusBar'
import { GameControls } from './GameControls'
import { ChatPanel } from './ChatPanel'
import { ErrorBoundary } from './ErrorBoundary'
import { TutorialModal } from './TutorialModal'

export default function App() {
  const game       = useGame()
  const [showModal, setShowModal]       = useState(true)   // New Game dialog
  const [showChat, setShowChat]         = useState(false)  // Referee chat panel
  const [showTutorial, setShowTutorial] = useState(false)  // How to Play overlay

  // Voice control integration — maps spoken commands to game actions
  const voice = useVoiceControl({
    gameState:    game.gameState,
    sessionId:    game.sessionId,
    onVoiceMove:  game.voiceMove,
    onVoicePush:  game.voicePush,
    onSkipMoves:  game.skipMoves,
  })

  /** Handle the "Start Game" action from the New Game modal. */
  const handleStart = async (mode, difficulty, playerColor) => {
    await game.createGame(mode, difficulty, playerColor)
    setShowModal(false)
  }

  return (
    <div className="app">
      {/* ─── Header ─── */}
      <header className="app-header">
        <div className="app-title-wrap">
          <h1 className="app-title">Push Fight</h1>
          <ConnectionPip status={game.connectionStatus} />
        </div>
        <div className="header-actions">
          <ThemeToggle />
          <button
            className="btn btn-ghost btn-small"
            onClick={() => setShowTutorial(true)}
            aria-label="How to play"
          >
            How to Play
          </button>
          {/* Session-specific controls only shown when a game is active */}
          {game.sessionId && (
            <>
              {voice.isSupported && (
                <button
                  className={`btn btn-ghost btn-small voice-toggle${voice.isListening ? ' voice-toggle--active' : ''}`}
                  onClick={voice.toggle}
                  aria-pressed={voice.isListening}
                  aria-label={voice.isListening ? 'Stop voice control' : 'Start voice control'}
                >
                  {voice.isListening ? 'Mic On' : 'Mic Off'}
                </button>
              )}
              <button
                className="btn btn-ghost btn-small"
                onClick={() => setShowChat(v => !v)}
                aria-pressed={showChat}
                aria-label="Toggle referee chat"
              >
                {showChat ? 'Hide Referee' : 'Ask Referee'}
              </button>
              <button
                className="btn btn-ghost btn-small"
                onClick={() => setShowModal(true)}
                aria-label="Start a new game"
              >
                New Game
              </button>
            </>
          )}
        </div>
      </header>

      {/* Voice command feedback toast */}
      {voice.lastCommand && (
        <div
          className={`voice-status voice-status--${voice.lastCommand.status}`}
          aria-live="polite"
        >
          {voice.lastCommand.status === 'err'
            ? `"${voice.lastCommand.text}" — ${voice.lastCommand.detail}`
            : voice.lastCommand.status === 'no-match'
            ? `"${voice.lastCommand.text}" — not recognised`
            : `"${voice.lastCommand.text}"`}
        </div>
      )}

      {/* Error toast — auto-dismissed after 3.5 seconds */}
      {game.error && (
        <div className="error-toast" role="alert" aria-live="assertive">
          {game.error}
        </div>
      )}

      <ErrorBoundary>
        {game.gameState ? (
          <main className="game-layout">
            {/* Board section — SVG game board with wood-texture wrapper */}
            <section className="board-panel" aria-label="Game board">
              <div className="board-wrap">
                <Board
                  gameState={game.gameState}
                  selectedPiece={game.selectedPiece}
                  validMoves={game.validMoves}
                  validPushDirs={game.validPushDirs}
                  pendingAiAction={game.pendingAiAction}
                  onCellClick={game.gameState.setupMode ? game.handleSetupCellClick : game.handleCellClick}
                  onPushDir={game.handlePushDir}
                  setupMode={game.gameState.setupMode}
                  setupPlayer={game.gameState.currentPlayer}
                />
              </div>
              <BoardLegend />
            </section>

            {/* Side panel — status, controls, optional chat */}
            <aside className="side-panel" aria-label="Game controls">
              <StatusBar gameState={game.gameState} aiThinking={game.aiThinking} />
              <GameControls
                gameState={game.gameState}
                selectedPiece={game.selectedPiece}
                validPushDirs={game.validPushDirs}
                onSkipMoves={game.skipMoves}
                onPushDir={game.handlePushDir}
                onNewGame={() => setShowModal(true)}
                sessionId={game.sessionId}
                onSave={game.saveGame}
                onLoad={game.loadSave}
                selectedSetupPiece={game.selectedSetupPiece}
                onSetupPieceSelect={game.setSelectedSetupPiece}
                onConfirmSetup={game.confirmSetup}
              />
              {showChat && (
                <ChatPanel messages={game.messages} onAsk={game.askReferee} />
              )}
            </aside>
          </main>
        ) : (
          <div className="empty-state">
            <p>Start a new game to begin.</p>
          </div>
        )}
      </ErrorBoundary>

      {/* New Game modal — shown on first load and when explicitly opened */}
      {showModal && (
        <NewGameModal
          onStart={handleStart}
          onClose={game.sessionId ? () => setShowModal(false) : null}
        />
      )}

      {/* Tutorial modal — rules explanation */}
      {showTutorial && (
        <TutorialModal onClose={() => setShowTutorial(false)} />
      )}

      <footer className="app-footer">
        <img src="/doug.svg" alt="Unicorn Delivery Service mascot" />
        <span>Powered by Unicorn Delivery Service</span>
      </footer>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ConnectionPip — small colored dot indicating WebSocket connection status
// ---------------------------------------------------------------------------

/**
 * Renders a small status indicator dot next to the app title.
 * States: 'idle' (grey), 'connected' (green), 'disconnected' (red/pulsing).
 */
function ConnectionPip({ status }) {
  const label = {
    idle:         'Not connected',
    connected:    'Connected',
    disconnected: 'Reconnecting…',
  }[status] ?? status

  return (
    <span
      className={`connection-pip connection-pip--${status}`}
      title={label}
      aria-label={`Connection status: ${label}`}
    />
  )
}

// ---------------------------------------------------------------------------
// NewGameModal — game configuration dialog
// ---------------------------------------------------------------------------

/**
 * Modal dialog for configuring a new game:
 *   - Game mode: PvP or PvAI
 *   - Player color (PvAI only): White or Black
 *   - AI difficulty (PvAI only): Easy, Medium, Hard
 *
 * The modal is dismissible (via Escape or clicking outside) only when
 * a game session already exists (onClose is non-null).
 */
function NewGameModal({ onStart, onClose }) {
  const [mode, setMode]             = useState('pvp')
  const [difficulty, setDiff]       = useState('medium')
  const [playerColor, setColor]     = useState('white')
  const [starting, setStarting]     = useState(false)

  const handleStart = async () => {
    setStarting(true)
    await onStart(mode, difficulty, playerColor)
    setStarting(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape' && onClose) onClose()
  }

  const aiColor = playerColor === 'white' ? 'Black' : 'White'
  const humanColor = playerColor === 'white' ? 'White' : 'Black'

  return (
    <div
      className="modal-overlay"
      onClick={onClose || undefined}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-label="New game setup"
    >
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>New Game</h2>
          {onClose && (
            <button className="modal-close" onClick={onClose} aria-label="Close dialog">✕</button>
          )}
        </div>

        <div className="modal-body">
          {/* Game mode selection */}
          <label className="field-label">Game mode</label>
          <div className="radio-group" role="radiogroup" aria-label="Game mode">
            {[['pvp', 'Player vs Player'], ['pvai', 'Player vs AI']].map(([val, label]) => (
              <label key={val} className={`radio-option ${mode === val ? 'selected' : ''}`}>
                <input type="radio" name="mode" value={val} checked={mode === val}
                  onChange={() => setMode(val)} />
                {label}
              </label>
            ))}
          </div>

          {/* AI-specific options (shown only in PvAI mode) */}
          {mode === 'pvai' && (
            <>
              <label className="field-label">Play as</label>
              <div className="radio-group" role="radiogroup" aria-label="Player colour">
                {[['white', 'White (goes first)'], ['black', 'Black (goes second)']].map(([val, label]) => (
                  <label key={val} className={`radio-option ${playerColor === val ? 'selected' : ''}`}>
                    <input type="radio" name="playerColor" value={val} checked={playerColor === val}
                      onChange={() => setColor(val)} />
                    {label}
                  </label>
                ))}
              </div>

              <label className="field-label">Difficulty</label>
              <div className="radio-group" role="radiogroup" aria-label="AI difficulty">
                {['easy', 'medium', 'hard'].map(d => (
                  <label key={d} className={`radio-option ${difficulty === d ? 'selected' : ''}`}>
                    <input type="radio" name="difficulty" value={d} checked={difficulty === d}
                      onChange={() => setDiff(d)} />
                    {d.charAt(0).toUpperCase() + d.slice(1)}
                  </label>
                ))}
              </div>
              <p className="modal-note">
                You play as <strong>{humanColor}</strong>. The AI plays as {aiColor}.
              </p>
            </>
          )}
        </div>

        <div className="modal-footer">
          <button
            className="btn btn-primary btn-large"
            onClick={handleStart}
            disabled={starting}
            aria-busy={starting}
          >
            {starting ? 'Starting…' : 'Start Game'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// BoardLegend — visual key showing piece shapes, colors, and anchor marker
// ---------------------------------------------------------------------------

/** Renders a compact legend bar below the board explaining piece types. */
function BoardLegend() {
  const items = [
    { color: '#f0e8d8', stroke: '#b89a60', shape: 'square', label: 'Sleeve / Lapel / Belt' },
    { color: '#f0e8d8', stroke: '#b89a60', shape: 'circle', label: 'Neck / Joint'  },
    { color: '#1e0e06', stroke: '#6a3818', shape: 'square', label: 'Sleeve / Lapel / Belt' },
    { color: '#1e0e06', stroke: '#6a3818', shape: 'circle', label: 'Neck / Joint'  },
    { color: '#ffd700', stroke: 'none',   shape: 'dot',    label: 'Anchor'       },
  ]
  return (
    <div className="board-legend" aria-label="Board legend">
      {items.map(({ color, stroke, shape, label }) => (
        <span key={label} className="legend-item">
          <svg width={18} height={18} aria-hidden="true">
            {shape === 'square' && <rect x={1} y={1} width={16} height={16} fill={color} stroke={stroke} strokeWidth={1.5} rx={3} />}
            {shape === 'circle' && <circle cx={9} cy={9} r={8}              fill={color} stroke={stroke} strokeWidth={1.5} />}
            {shape === 'dot'    && <circle cx={9} cy={9} r={5}              fill={color} />}
          </svg>
          <span>{label}</span>
        </span>
      ))}
    </div>
  )
}
