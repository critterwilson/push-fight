import { useState, useEffect } from 'react'
import * as api from './api'

export function GameControls({
  gameState, selectedPiece, validPushDirs,
  onSkipMoves, onPushDir, onNewGame, sessionId,
  onSave, onLoad,
}) {
  const [saveInput, setSaveInput]   = useState('')
  const [saves, setSaves]           = useState([])
  const [showSaveLoad, setShowSaveLoad] = useState(false)
  const [saveMsg, setSaveMsg]       = useState('')

  const isPushPhase  = !gameState.canMove && gameState.canPush && !gameState.gameOver
  const isPlayerTurn = !gameState.isAiTurn && !gameState.gameOver

  // Check which push directions are valid
  const canUp    = validPushDirs.some(([dy]) => dy === -1)
  const canDown  = validPushDirs.some(([dy]) => dy ===  1)
  const canLeft  = validPushDirs.some(([, dx]) => dx === -1)
  const canRight = validPushDirs.some(([, dx]) => dx ===  1)

  const loadSaveList = async () => {
    const data = await api.listSaves()
    setSaves(data.saves)
  }

  const handleToggleSaveLoad = () => {
    if (!showSaveLoad) loadSaveList()
    setShowSaveLoad(v => !v)
  }

  const handleSave = async () => {
    const name = saveInput.trim() || 'game'
    await onSave(name)
    setSaveMsg(`Saved as "${name}"`)
    setTimeout(() => setSaveMsg(''), 2500)
    loadSaveList()
  }

  const handleLoad = async (name) => {
    await onLoad(name)
    setShowSaveLoad(false)
  }

  return (
    <div className="game-controls">

      {/* Skip to push */}
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
              <button className="dir-btn" disabled={!canUp}    onClick={() => onPushDir(-1,  0)}>↑</button>
              <div />
              <button className="dir-btn" disabled={!canLeft}  onClick={() => onPushDir( 0, -1)}>←</button>
              <div className="dir-center" />
              <button className="dir-btn" disabled={!canRight} onClick={() => onPushDir( 0,  1)}>→</button>
              <div />
              <button className="dir-btn" disabled={!canDown}  onClick={() => onPushDir( 1,  0)}>↓</button>
              <div />
            </div>
          )}
        </div>
      )}

      {/* Bottom controls */}
      <div className="bottom-controls">
        <button className="btn btn-primary" onClick={onNewGame}>New game</button>
        <button className="btn btn-ghost"   onClick={handleToggleSaveLoad}>
          {showSaveLoad ? 'Close' : 'Save / Load'}
        </button>
      </div>

      {/* Save/Load panel */}
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
