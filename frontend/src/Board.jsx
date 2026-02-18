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
  killZoneFill:     'rgba(0,0,0,0.38)',
  validMoveDot:     'rgba(0, 85, 212, 0.65)',
  selBorder:        '#ffd700',
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
  const W = 10 * CELL
  const H = 4 * CELL
  const GUTTER_LEFT = 20
  const GUTTER_TOP  = 20

  return (
    <svg
      width={W + GUTTER_LEFT} height={H + GUTTER_TOP}
      viewBox={`${-GUTTER_LEFT} ${-GUTTER_TOP} ${W + GUTTER_LEFT} ${H + GUTTER_TOP}`}
      style={{ display: 'block' }}
      role="application"
      aria-label="Push Fight board, landscape: 10 columns wide, 4 rows tall"
    >
      {/* Column labels A–D — left side (y-axis after transposing) */}
      {COL_LETTERS.map((letter, x) => (
        <text
          key={letter}
          x={-GUTTER_LEFT / 2 - 1} y={x * CELL + CELL / 2}
          textAnchor="middle" dominantBaseline="middle"
          fontSize={12} fontFamily="system-ui, sans-serif"
          fill="rgba(180,120,60,0.85)"
          aria-hidden="true"
        >
          {letter}
        </text>
      ))}

      {/* Row labels 1–10 — top (x-axis after transposing) */}
      {Array.from({ length: 10 }, (_, y) => (
        <text
          key={y}
          x={y * CELL + CELL / 2} y={-GUTTER_TOP / 2 - 1}
          textAnchor="middle" dominantBaseline="middle"
          fontSize={12} fontFamily="system-ui, sans-serif"
          fill="rgba(180,120,60,0.85)"
          aria-hidden="true"
        >
          {y + 1}
        </text>
      ))}

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

      {/* Centre line — vertical after transposing */}
      <line
        x1={4.5 * CELL} y1={0} x2={4.5 * CELL} y2={H}
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

const COL_LETTERS = ['A', 'B', 'C', 'D']

function cellCoord(y, x) {
  return `${COL_LETTERS[x]}${y + 1}`
}

function cellAriaLabel(cell, y, x) {
  const coord = cellCoord(y, x)
  if (cell.killZone) return `Kill zone ${coord}`
  if (!cell.piece)   return `Empty cell ${coord}`
  const name   = cell.piece.name ? cell.piece.name.charAt(0).toUpperCase() + cell.piece.name.slice(1) : cell.piece.team
  const anchor = cell.isAnchor ? ', anchored' : ''
  return `${name} (${cell.piece.team})${anchor}, ${coord}`
}

function BoardCell({ cell, y, x, isSelected, isValidMove, isAiHighlighted, onCellClick }) {
  const { killZone, piece, isAnchor } = cell

  const fill = killZone
    ? C.killZoneFill
    : isSelected
    ? 'rgba(255, 215, 0, 0.2)'
    : 'transparent'
  const borderColor = isSelected
    ? C.selBorder
    : isAiHighlighted
    ? C.aiHighlight
    : 'rgba(0, 0, 0, 0.15)'
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
        x={y * CELL + 1} y={x * CELL + 1}
        width={CELL - 2} height={CELL - 2}
        fill={fill}
        stroke={borderColor} strokeWidth={borderW}
        rx={3}
      />

      {/* AI pending-action glow */}
      {isAiHighlighted && (
        <rect
          x={y * CELL + 1} y={x * CELL + 1}
          width={CELL - 2} height={CELL - 2}
          fill={C.aiHighlightGlow} rx={3}
          pointerEvents="none"
          style={{ animation: 'aiPulse 0.8s ease-in-out infinite alternate' }}
        />
      )}

      {/* Valid move indicator */}
      {isValidMove && !piece && (
        <circle
          cx={y * CELL + CELL / 2} cy={x * CELL + CELL / 2}
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
  const cx      = y * CELL + CELL / 2
  const cy      = x * CELL + CELL / 2
  const size    = CELL - pad * 2
  const label   = piece.name ? piece.name : (isWhite ? 'W' : 'B')
  const pieceName = piece.name ? piece.name.charAt(0).toUpperCase() + piece.name.slice(1) : (isWhite ? 'White' : 'Black')

  return (
    <g pointerEvents="none" aria-hidden="true">
      <title>{pieceName} ({piece.team}) — {cellCoord(y, x)}</title>
      {piece.shape === 'square' ? (
        <rect
          x={y * CELL + pad} y={x * CELL + pad}
          width={size} height={size}
          fill={fill} stroke={stroke} strokeWidth={2.5} rx={8}
        />
      ) : (
        <circle
          cx={cx} cy={cy} r={size / 2}
          fill={fill} stroke={stroke} strokeWidth={2.5}
        />
      )}

      {/* Piece full name */}
      <text
        x={cx} y={cy + 1}
        textAnchor="middle" dominantBaseline="middle"
        fontSize={8} fontWeight="bold" fontFamily="system-ui, sans-serif"
        fill={isWhite ? '#7a5a28' : '#c89060'}
        className={`piece-label ${isWhite ? 'piece-label-white' : 'piece-label-black'}`}
      >
        {label}
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

  // Board is transposed: SVG x-axis = game row (py), SVG y-axis = game col (px)
  const svgCX = py * CELL + CELL / 2
  const svgCY = px * CELL + CELL / 2
  let tipX, tipY
  // dy=-1 (game row decreases) → visual left  (SVG x decreases)
  if      (dy === -1) { tipX = py * CELL + MARGIN;        tipY = svgCY }
  // dy=+1 (game row increases) → visual right (SVG x increases)
  else if (dy ===  1) { tipX = py * CELL + CELL - MARGIN; tipY = svgCY }
  // dx=-1 (game col decreases) → visual up    (SVG y decreases)
  else if (dx === -1) { tipX = svgCX;                     tipY = px * CELL + MARGIN }
  // dx=+1 (game col increases) → visual down  (SVG y increases)
  else                { tipX = svgCX;                     tipY = px * CELL + CELL - MARGIN }

  // Visual direction vector after transposition: (vx, vy) = (dy, dx)
  const pts = [
    [tipX,                          tipY                         ],
    [tipX - dy * S - dx * S * 0.6, tipY - dx * S + dy * S * 0.6],
    [tipX - dy * S + dx * S * 0.6, tipY - dx * S - dy * S * 0.6],
  ].map(([a, b]) => `${a.toFixed(1)},${b.toFixed(1)}`).join(' ')

  const HIT = CELL / 2
  const hx  = dy === -1 ? py * CELL : dy === 1 ? py * CELL + HIT : py * CELL + CELL / 4
  const hy  = dx === -1 ? px * CELL : dx === 1 ? px * CELL + HIT : px * CELL + CELL / 4
  const hw  = dy !== 0 ? HIT : CELL / 2
  const hh  = dx !== 0 ? HIT : CELL / 2

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
