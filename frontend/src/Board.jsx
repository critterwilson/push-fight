/**
 * Board — SVG renderer for the Push Fight board.
 *
 * Board layout : 10 rows × 4 cols, each cell 64×64 px.
 * Kill zones   : rows 0 & 9 (and irregular corners per grid definition).
 * Centre line  : dashed line between rows 4 and 5.
 * Push arrows  : appear at the edges of the selected piece's cell.
 * AI highlight : the piece involved in a pending AI action pulses orange.
 */

const CELL = 64

const C = {
  killZone:         '#0e1014',
  playable:         '#253d1e',
  selected:         '#1e4d2e',
  validMoveDot:     'rgba(60, 220, 120, 0.65)',
  selBorder:        '#ffd700',
  cellBorder:       '#192e14',
  pieceWhite:       '#f0e8d8',
  pieceWhiteStroke: '#b89a60',
  pieceBlack:       '#1e0e06',
  pieceBlackStroke: '#6a3818',
  anchor:           '#ffd700',
  centerLine:       'rgba(255,255,255,0.15)',
  pushArrow:        '#ff6b1a',
  pushArrowGlow:    'rgba(255, 107, 26, 0.3)',
  aiHighlight:      '#ff6b1a',
  aiHighlightGlow:  'rgba(255, 107, 26, 0.25)',
}

export function Board({
  gameState, selectedPiece, validMoves, validPushDirs,
  pendingAiAction, onCellClick, onPushDir,
}) {
  const W = 4 * CELL
  const H = 10 * CELL

  return (
    <svg
      width={W} height={H}
      viewBox={`0 0 ${W} ${H}`}
      style={{ display: 'block' }}
      role="application"
      aria-label="Push Fight board, 10 rows by 4 columns"
    >
      {gameState.board.map((row, y) =>
        row.map((cell, x) => {
          const isSel = selectedPiece?.[0] === y && selectedPiece?.[1] === x
          const isVM  = !cell.killZone && validMoves.some(([my, mx]) => my === y && mx === x)

          // AI action highlighting
          const isAiSrc = pendingAiAction?.type === 'move'
            && pendingAiAction.from[0] === y && pendingAiAction.from[1] === x
          const isAiPusher = pendingAiAction?.type === 'push'
            && pendingAiAction.piece[0] === y && pendingAiAction.piece[1] === x
          const isAiHighlighted = isAiSrc || isAiPusher

          return (
            <BoardCell
              key={`${y}-${x}`}
              cell={cell} y={y} x={x}
              isSelected={isSel}
              isValidMove={isVM}
              isAiHighlighted={isAiHighlighted}
              onCellClick={onCellClick}
            />
          )
        })
      )}

      {/* Centre line */}
      <line
        x1={0} y1={4.5 * CELL} x2={W} y2={4.5 * CELL}
        stroke={C.centerLine} strokeWidth={2} strokeDasharray="6 4"
        pointerEvents="none"
        aria-hidden="true"
      />

      {/* Push-direction arrows */}
      {selectedPiece && validPushDirs.map(([dy, dx]) => (
        <PushArrow
          key={`${dy},${dx}`}
          py={selectedPiece[0]} px={selectedPiece[1]}
          dy={dy} dx={dx}
          onPushDir={onPushDir}
        />
      ))}
    </svg>
  )
}

// ---------------------------------------------------------------------------
// BoardCell
// ---------------------------------------------------------------------------

function cellAriaLabel(cell, y, x) {
  const row = y + 1
  const col = x + 1
  if (cell.killZone) return `Kill zone, row ${row}, column ${col}`
  if (!cell.piece)   return `Empty cell, row ${row}, column ${col}`
  const anchor = cell.isAnchor ? ', anchored' : ''
  return `${cell.piece.team} ${cell.piece.shape} piece${anchor}, row ${row}, column ${col}`
}

function BoardCell({ cell, y, x, isSelected, isValidMove, isAiHighlighted, onCellClick }) {
  const { killZone, piece, isAnchor } = cell

  const fill = killZone ? C.killZone : isSelected ? C.selected : C.playable
  const borderColor = isSelected
    ? C.selBorder
    : isAiHighlighted
    ? C.aiHighlight
    : killZone
    ? C.killZone
    : C.cellBorder
  const borderW = isSelected || isAiHighlighted ? 2.5 : 1

  const handleKey = (e) => {
    if (!killZone && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault()
      onCellClick(y, x)
    }
  }

  return (
    <g
      onClick={() => !killZone && onCellClick(y, x)}
      onKeyDown={handleKey}
      tabIndex={killZone ? -1 : 0}
      role={killZone ? undefined : 'button'}
      aria-label={cellAriaLabel(cell, y, x)}
      aria-pressed={isSelected ? true : undefined}
      data-row={y}
      data-col={x}
      style={{ cursor: killZone ? 'default' : 'pointer', outline: 'none' }}
    >
      <rect
        x={x * CELL + 1} y={y * CELL + 1}
        width={CELL - 2} height={CELL - 2}
        fill={fill}
        stroke={borderColor} strokeWidth={borderW}
        rx={3}
      />

      {/* AI pending-action glow */}
      {isAiHighlighted && (
        <rect
          x={x * CELL + 1} y={y * CELL + 1}
          width={CELL - 2} height={CELL - 2}
          fill={C.aiHighlightGlow} rx={3}
          pointerEvents="none"
          style={{ animation: 'aiPulse 0.8s ease-in-out infinite alternate' }}
        />
      )}

      {/* Valid move indicator */}
      {isValidMove && !piece && (
        <circle
          cx={x * CELL + CELL / 2} cy={y * CELL + CELL / 2}
          r={11} fill={C.validMoveDot}
          pointerEvents="none"
          aria-hidden="true"
        />
      )}

      {/* Piece */}
      {piece && !killZone && (
        <GamePiece piece={piece} x={x} y={y} isAnchor={isAnchor} />
      )}
    </g>
  )
}

// ---------------------------------------------------------------------------
// GamePiece
// ---------------------------------------------------------------------------

function GamePiece({ piece, x, y, isAnchor }) {
  const isWhite = piece.team === 'white'
  const fill    = isWhite ? C.pieceWhite    : C.pieceBlack
  const stroke  = isWhite ? C.pieceWhiteStroke : C.pieceBlackStroke
  const pad     = 9
  const cx      = x * CELL + CELL / 2
  const cy      = y * CELL + CELL / 2
  const size    = CELL - pad * 2

  return (
    <g pointerEvents="none" aria-hidden="true">
      {piece.shape === 'square' ? (
        <rect
          x={x * CELL + pad} y={y * CELL + pad}
          width={size} height={size}
          fill={fill} stroke={stroke} strokeWidth={2.5} rx={8}
        />
      ) : (
        <circle
          cx={cx} cy={cy} r={size / 2}
          fill={fill} stroke={stroke} strokeWidth={2.5}
        />
      )}

      {/* Team label */}
      <text
        x={cx} y={cy + 1}
        textAnchor="middle" dominantBaseline="middle"
        fontSize={13} fontWeight="bold" fontFamily="system-ui, sans-serif"
        fill={isWhite ? '#7a5a28' : '#c89060'}
      >
        {piece.team === 'white' ? 'W' : 'B'}
      </text>

      {/* Anchor gold dot */}
      {isAnchor && (
        <>
          <circle cx={cx} cy={cy} r={7} fill="rgba(0,0,0,0.3)" />
          <circle cx={cx} cy={cy} r={5} fill={C.anchor} opacity={0.92} />
        </>
      )}
    </g>
  )
}

// ---------------------------------------------------------------------------
// PushArrow — click target at each cell edge for valid push directions
// ---------------------------------------------------------------------------

function PushArrow({ py, px, dy, dx, onPushDir }) {
  const MARGIN = 9
  const S      = 12

  const cx  = px * CELL + CELL / 2
  const cy  = py * CELL + CELL / 2
  let tipX, tipY
  if      (dy === -1) { tipX = cx;                        tipY = py * CELL + MARGIN }
  else if (dy ===  1) { tipX = cx;                        tipY = py * CELL + CELL - MARGIN }
  else if (dx === -1) { tipX = px * CELL + MARGIN;        tipY = cy }
  else                { tipX = px * CELL + CELL - MARGIN; tipY = cy }

  const pts = [
    [tipX,                          tipY                         ],
    [tipX - dx * S - dy * S * 0.6, tipY - dy * S + dx * S * 0.6],
    [tipX - dx * S + dy * S * 0.6, tipY - dy * S - dx * S * 0.6],
  ].map(([a, b]) => `${a.toFixed(1)},${b.toFixed(1)}`).join(' ')

  const HIT = CELL / 2
  const hx  = dx === -1 ? px * CELL : dx === 1 ? px * CELL + HIT : px * CELL + CELL / 4
  const hy  = dy === -1 ? py * CELL : dy === 1 ? py * CELL + HIT : py * CELL + CELL / 4
  const hw  = dx !== 0 ? HIT : CELL / 2
  const hh  = dy !== 0 ? HIT : CELL / 2

  const dirLabel = dy === -1 ? 'up' : dy === 1 ? 'down' : dx === -1 ? 'left' : 'right'

  return (
    <g
      onClick={(e) => { e.stopPropagation(); onPushDir(dy, dx) }}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPushDir(dy, dx) } }}
      tabIndex={0}
      role="button"
      aria-label={`Push ${dirLabel}`}
      style={{ cursor: 'pointer', outline: 'none' }}
    >
      <rect x={hx} y={hy} width={hw} height={hh} fill="transparent" />
      <circle cx={tipX} cy={tipY} r={15} fill={C.pushArrowGlow} />
      <polygon points={pts} fill={C.pushArrow} stroke="#ffaa60" strokeWidth={1} />
    </g>
  )
}
