export function StatusBar({ gameState, aiThinking }) {
  const {
    currentPlayer, canMove, movesMade,
    gameOver, winner, piecesPushedOff, mode, aiTeam,
  } = gameState

  const isAiPlayer = mode === 'pvai' && currentPlayer === aiTeam

  // Phase label
  let phase = ''
  if (!gameOver) {
    if (canMove) {
      const remaining = 2 - movesMade
      phase = `Move phase — ${remaining} move${remaining !== 1 ? 's' : ''} left`
    } else {
      phase = 'Push phase — select a square piece'
    }
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

      <div className="pieces-lost-row">
        <PiecesLost label="White lost" data={piecesPushedOff.white} team="white" />
        <PiecesLost label="Black lost" data={piecesPushedOff.black} team="black" />
      </div>
    </div>
  )
}

function PiecesLost({ label, data, team }) {
  const { squares, rounds } = data
  if (squares === 0 && rounds === 0) return null

  const sqColor  = team === 'white' ? '#f0e8d8' : '#4a2010'
  const rdColor  = team === 'white' ? '#f0e8d8' : '#4a2010'
  const stroke   = team === 'white' ? '#b89a60' : '#6a3818'

  return (
    <div className="pieces-lost">
      <span className="pieces-lost-label">{label}:</span>
      <svg width={(squares + rounds) * 22} height={20} style={{ verticalAlign: 'middle' }}>
        {Array.from({ length: squares }).map((_, i) => (
          <rect key={`s${i}`} x={i * 22 + 1} y={2} width={18} height={16}
            fill={sqColor} stroke={stroke} strokeWidth={1.5} rx={3} />
        ))}
        {Array.from({ length: rounds }).map((_, i) => (
          <circle key={`r${i}`} cx={(squares + i) * 22 + 10} cy={10} r={8}
            fill={rdColor} stroke={stroke} strokeWidth={1.5} />
        ))}
      </svg>
    </div>
  )
}
