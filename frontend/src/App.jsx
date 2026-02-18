import { useState } from 'react'
import { useGame } from './useGame'
import { Board } from './Board'
import { StatusBar } from './StatusBar'
import { GameControls } from './GameControls'
import { ChatPanel } from './ChatPanel'
import { ErrorBoundary } from './ErrorBoundary'

export default function App() {
  const game       = useGame()
  const [showModal, setShowModal] = useState(true)
  const [showChat, setShowChat]   = useState(false)

  const handleStart = async (mode, difficulty) => {
    await game.createGame(mode, difficulty)
    setShowModal(false)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">Push Fight</h1>
        <div className="header-actions">
          <ConnectionPip status={game.connectionStatus} />
          {game.sessionId && (
            <>
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

      {/* Error toast */}
      {game.error && (
        <div className="error-toast" role="alert" aria-live="assertive">
          {game.error}
        </div>
      )}

      <ErrorBoundary>
        {game.gameState ? (
          <main className="game-layout">
            {/* Board */}
            <section className="board-panel" aria-label="Game board">
              <div className="board-wrap">
                <Board
                  gameState={game.gameState}
                  selectedPiece={game.selectedPiece}
                  validMoves={game.validMoves}
                  validPushDirs={game.validPushDirs}
                  pendingAiAction={game.pendingAiAction}
                  onCellClick={game.handleCellClick}
                  onPushDir={game.handlePushDir}
                />
              </div>
              <BoardLegend />
            </section>

            {/* Side panel */}
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

      {/* New Game modal */}
      {showModal && (
        <NewGameModal
          onStart={handleStart}
          onClose={game.sessionId ? () => setShowModal(false) : null}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Connection status pip
// ---------------------------------------------------------------------------

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
// New Game Modal
// ---------------------------------------------------------------------------

function NewGameModal({ onStart, onClose }) {
  const [mode, setMode]         = useState('pvp')
  const [difficulty, setDiff]   = useState('medium')
  const [starting, setStarting] = useState(false)

  const handleStart = async () => {
    setStarting(true)
    await onStart(mode, difficulty)
    setStarting(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape' && onClose) onClose()
  }

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

          {mode === 'pvai' && (
            <>
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
                You play as <strong>White</strong>. The AI plays as Black.
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
// Board legend
// ---------------------------------------------------------------------------

function BoardLegend() {
  const items = [
    { color: '#f0e8d8', stroke: '#b89a60', shape: 'square', label: 'White square' },
    { color: '#f0e8d8', stroke: '#b89a60', shape: 'circle', label: 'White round'  },
    { color: '#1e0e06', stroke: '#6a3818', shape: 'square', label: 'Black square' },
    { color: '#1e0e06', stroke: '#6a3818', shape: 'circle', label: 'Black round'  },
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
