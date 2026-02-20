/**
 * GameControls — Side-panel controls for game actions.
 *
 * Renders different control sets depending on the game phase:
 *
 *   **Setup mode**: Shows the SetupTray (piece palette) and a confirm
 *   button.  The tray lists all 5 pieces with their shapes; placed
 *   pieces are greyed out, and the selected piece is highlighted.
 *
 *   **Play mode**: Shows phase-specific controls:
 *     - Move phase: "Skip moves → Push now" button.
 *     - Push phase: Direction pad (arrow buttons) for selecting
 *       push direction when a square piece is selected.
 *     - Bottom controls: "New game" and "Save / Load" toggle.
 *     - Save/Load panel: Save input field + list of saved games.
 *
 * The direction pad maps visual directions to game coordinates,
 * accounting for the board's transposition:
 *   Visual up/down    → dx changes (column axis)
 *   Visual left/right → dy changes (row axis)
 */

import { useState, useEffect } from 'react'
import * as api from './api'

export function GameControls({
  gameState, selectedPiece, validPushDirs,
  onSkipMoves, onPushDir, onNewGame, sessionId,
  onSave, onLoad,
  selectedSetupPiece, onSetupPieceSelect, onConfirmSetup,
}) {
  const [saveInput, setSaveInput]   = useState('')
  const [saves, setSaves]           = useState([])
  const [showSaveLoad, setShowSaveLoad] = useState(false)
  const [saveMsg, setSaveMsg]       = useState('')

  // Derived state for rendering conditions
  const isPushPhase  = !gameState.canMove && gameState.canPush && !gameState.gameOver
  const isPlayerTurn = !gameState.isAiTurn && !gameState.gameOver

  // Map valid push directions to visual button states.
  // Board is transposed: dy changes = left/right, dx changes = up/down.
  const canUp    = validPushDirs.some(([, dx]) => dx === -1)
  const canDown  = validPushDirs.some(([, dx]) => dx ===  1)
  const canLeft  = validPushDirs.some(([dy])   => dy === -1)
  const canRight = validPushDirs.some(([dy])   => dy ===  1)

  /** Fetch the list of saved games from the server. */
  const loadSaveList = async () => {
    const data = await api.listSaves()
    setSaves(data.saves)
  }

  /** Toggle the save/load panel visibility, fetching saves on open. */
  const handleToggleSaveLoad = () => {
    if (!showSaveLoad) loadSaveList()
    setShowSaveLoad(v => !v)
  }

  /** Save the current game with the given name and show confirmation. */
  const handleSave = async () => {
    const name = saveInput.trim() || 'game'
    await onSave(name)
    setSaveMsg(`Saved as "${name}"`)
    setTimeout(() => setSaveMsg(''), 2500)
    loadSaveList()
  }

  /** Load a saved game by name and close the panel. */
  const handleLoad = async (name) => {
    await onLoad(name)
    setShowSaveLoad(false)
  }

  // ── Setup mode UI ─────────────────────────────────────────────────────

  if (gameState.setupMode) {
    const team   = gameState.currentPlayer
    const status = gameState.placementStatus?.[team] ?? { unplaced: [] }
    const allPlaced = status.unplaced.length === 0

    return (
      <div className="game-controls">
        <SetupTray
          team={team}
          unplaced={status.unplaced}
          selectedPiece={selectedSetupPiece}
          onSelect={onSetupPieceSelect}
        />
        <button
          className="btn btn-primary full-width"
          disabled={!allPlaced}
          onClick={onConfirmSetup}
        >
          {allPlaced ? 'Confirm placement →' : `Place ${status.unplaced.length} more piece${status.unplaced.length !== 1 ? 's' : ''}…`}
        </button>
        <div className="bottom-controls">
          <button className="btn btn-primary" onClick={onNewGame}>New game</button>
        </div>
      </div>
    )
  }

  // ── Play mode UI ──────────────────────────────────────────────────────

  return (
    <div className="game-controls">

      {/* Skip to push — shown during move phase on the player's turn */}
      {isPlayerTurn && gameState.canMove && (
        <button className="btn btn-secondary full-width" onClick={onSkipMoves}>
          Skip moves → Push now
        </button>
      )}

      {/* Direction pad — shown when a square piece is selected in push phase */}
      {isPushPhase && (
        <div className="push-section">
          <div className="push-label">
            {selectedPiece ? 'Choose push direction:' : 'Select a square piece to push'}
          </div>
          {selectedPiece && (
            <div className="dir-pad">
              <div />
              <button className="dir-btn" disabled={!canUp}    onClick={() => onPushDir( 0, -1)}>↑</button>
              <div />
              <button className="dir-btn" disabled={!canLeft}  onClick={() => onPushDir(-1,  0)}>←</button>
              <div className="dir-center" />
              <button className="dir-btn" disabled={!canRight} onClick={() => onPushDir( 1,  0)}>→</button>
              <div />
              <button className="dir-btn" disabled={!canDown}  onClick={() => onPushDir( 0,  1)}>↓</button>
              <div />
            </div>
          )}
        </div>
      )}

      {/* Bottom controls — always visible during play */}
      <div className="bottom-controls">
        <button className="btn btn-primary" onClick={onNewGame}>New game</button>
        <button className="btn btn-ghost"   onClick={handleToggleSaveLoad}>
          {showSaveLoad ? 'Close' : 'Save / Load'}
        </button>
      </div>

      {/* Save/Load collapsible panel */}
      {showSaveLoad && (
        <div className="save-load-panel">
          <div className="save-row">
            <input
              className="save-input"
              placeholder="Save name…"
              value={saveInput}
              onChange={e => setSaveInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSave()}
            />
            <button className="btn btn-small" onClick={handleSave}>Save</button>
          </div>
          {saveMsg && <div className="save-msg">{saveMsg}</div>}

          {saves.length > 0 && (
            <div className="saves-list">
              <div className="saves-list-label">Saved games:</div>
              {saves.map(name => (
                <div key={name} className="save-item">
                  <span className="save-name">{name}</span>
                  <button className="btn btn-small btn-ghost" onClick={() => handleLoad(name)}>
                    Load
                  </button>
                </div>
              ))}
            </div>
          )}
          {saves.length === 0 && <div className="saves-empty">No saved games</div>}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// SetupTray — piece palette shown during the placement phase
// ---------------------------------------------------------------------------

/** Maps piece names to their shapes (square = pusher, round = non-pusher). */
const PIECE_SHAPE = { sleeve: 'square', lapel: 'square', belt: 'square', neck: 'round', joint: 'round' }

/** All five piece names in display order. */
const ALL_PIECES  = ['sleeve', 'lapel', 'belt', 'neck', 'joint']

/**
 * SetupTray — horizontal row of piece chips for setup placement.
 *
 * Each chip shows the piece's shape (square or circle SVG), its name,
 * and its placement status (placed = greyed out, selected = highlighted).
 *
 * @param {string}   team          — Current team placing pieces.
 * @param {string[]} unplaced      — Names of pieces not yet placed.
 * @param {string}   selectedPiece — Currently selected piece name, or null.
 * @param {function} onSelect      — Callback when a piece chip is clicked.
 */
function SetupTray({ team, unplaced, selectedPiece, onSelect }) {
  const isWhite = team === 'white'
  const label   = isWhite ? 'White — place your pieces' : 'Black — place your pieces'

  return (
    <div className="setup-tray">
      <div className="setup-tray-label">{label}</div>
      <div className="setup-tray-pieces">
        {ALL_PIECES.map(name => {
          const placed   = !unplaced.includes(name)
          const selected = selectedPiece === name
          const shape    = PIECE_SHAPE[name]
          return (
            <button
              key={name}
              className={`setup-piece-chip${selected ? ' selected' : ''}${placed ? ' placed' : ''}`}
              onClick={() => !placed && onSelect(selected ? null : name)}
              disabled={placed}
              aria-pressed={selected}
              title={placed ? `${name} — placed` : `Select ${name}`}
            >
              {/* Piece shape icon */}
              <svg width={20} height={20} aria-hidden="true">
                {shape === 'square'
                  ? <rect x={2} y={2} width={16} height={16} rx={4}
                      fill={isWhite ? '#f0e8d8' : '#1e0e06'}
                      stroke={isWhite ? '#b89a60' : '#6a3818'} strokeWidth={1.5} />
                  : <circle cx={10} cy={10} r={8}
                      fill={isWhite ? '#f0e8d8' : '#1e0e06'}
                      stroke={isWhite ? '#b89a60' : '#6a3818'} strokeWidth={1.5} />
                }
              </svg>
              <span>{name}</span>
            </button>
          )
        })}
      </div>
      <p className="setup-tray-hint">
        {selectedPiece
          ? `Click a highlighted cell to place ${selectedPiece}`
          : 'Select a piece, then click a cell on your half'}
      </p>
    </div>
  )
}
