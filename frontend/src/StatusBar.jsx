/**
 * StatusBar — Displays current turn information and eliminated pieces.
 *
 * Shows:
 *   - Whose turn it is (with team color badge)
 *   - Current phase (move or push) with remaining move count
 *   - AI thinking indicator when the RL agent is processing
 *   - Game-over banner when a winner is determined
 *   - Pieces-lost row: SVG icons of eliminated pieces per team
 */

/**
 * Main status bar component.
 *
 * @param {object} gameState — The current game state from the server.
 * @param {boolean} aiThinking — True when the AI is processing its turn.
 */
export function StatusBar({ gameState, aiThinking }) {
  const {
    currentPlayer, canMove, movesMade,
    gameOver, winner, piecesPushedOff, mode, aiTeam,
  } = gameState

  const isAiPlayer = mode === 'pvai' && currentPlayer === aiTeam

  // Build the phase label (hidden during AI turns and game over)
  let phase = ''
  if (!gameOver) {
    if (canMove) {
      const remaining = 2 - movesMade
      phase = `Move phase — ${remaining} move${remaining !== 1 ? 's' : ''} left`
    } else {
      phase = 'Push phase — select a square piece'
    }
    // Suppress phase label during AI thinking
    if (isAiPlayer || aiThinking) phase = ''
  }

  return (
    <div className="status-bar">
      {gameOver ? (
        <div className={`winner-banner winner-${winner}`}>
          {winner === 'white' ? 'White' : 'Black'} wins!
        </div>
      ) : (
        <div className="turn-info">
          {aiThinking ? (
            <span className="ai-thinking">AI is thinking…</span>
          ) : (
            <span className={`player-tag player-${currentPlayer}`}>
              {currentPlayer === 'white' ? 'White' : 'Black'}
              {isAiPlayer ? ' (AI)' : ''}&apos;s turn
            </span>
          )}
          {phase && <span className="phase-label">{phase}</span>}
        </div>
      )}

      {/* Eliminated pieces summary for both teams */}
      <div className="pieces-lost-row">
        <PiecesLost label="White lost" data={piecesPushedOff.white} team="white" />
        <PiecesLost label="Black lost" data={piecesPushedOff.black} team="black" />
      </div>
    </div>
  )
}

/**
 * PiecesLost — Renders SVG icons of eliminated pieces for one team.
 *
 * Displays square icons for eliminated square pieces and circle icons
 * for eliminated round pieces.  Hidden when no pieces have been lost.
 */
function PiecesLost({ label, data, team }) {
  const { squares, rounds } = data
  if (squares === 0 && rounds === 0) return null

  // Piece colors match the board rendering
  const sqColor  = team === 'white' ? '#f0e8d8' : '#4a2010'
  const rdColor  = team === 'white' ? '#f0e8d8' : '#4a2010'
  const stroke   = team === 'white' ? '#b89a60' : '#6a3818'

  return (
    <div className="pieces-lost">
      <span className="pieces-lost-label">{label}:</span>
      <svg width={(squares + rounds) * 22} height={20} style={{ verticalAlign: 'middle' }}>
        {/* Render a square icon for each eliminated square piece */}
        {Array.from({ length: squares }).map((_, i) => (
          <rect key={`s${i}`} x={i * 22 + 1} y={2} width={18} height={16}
            fill={sqColor} stroke={stroke} strokeWidth={1.5} rx={3} />
        ))}
        {/* Render a circle icon for each eliminated round piece */}
        {Array.from({ length: rounds }).map((_, i) => (
          <circle key={`r${i}`} cx={(squares + i) * 22 + 10} cy={10} r={8}
            fill={rdColor} stroke={stroke} strokeWidth={1.5} />
        ))}
      </svg>
    </div>
  )
}
