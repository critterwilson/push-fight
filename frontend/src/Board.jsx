/**
 * Board — SVG renderer for the Push Fight game board.
 *
 * Renders a 10-row × 4-column grid in landscape orientation using SVG.
 * Each cell is 64×64 pixels.
 *
 * Board coordinate transposition:
 *   The board data model uses [y][x] where y=row (0–9 north–south) and
 *   x=column (0–3 west–east).  In the SVG, the board is rotated so that:
 *     - Game rows (y-axis) map to the SVG x-axis (left → right)
 *     - Game columns (x-axis) map to the SVG y-axis (top → bottom)
 *   This gives a landscape layout: 10 columns wide × 4 rows tall.
 *
 * Visual elements:
 *   - Kill zones: dark overlay cells at board edges
 *   - Center line: dashed vertical line between columns 4 and 5
 *   - Pieces: square (pushers) and round (non-pushers) with BJJ names
 *   - Selection: gold border on the selected piece
 *   - Valid moves: blue dots on reachable cells
 *   - Push arrows: orange triangular click targets at cell edges
 *   - AI highlights: pulsing orange glow on AI-active pieces
 *   - Setup targets: dashed green borders on valid placement cells
 *   - Anchor: gold dot centered on the anchored piece
 *   - Column labels (A–D) and row labels (1–10) for voice control
 */

const CELL = 64  // Cell size in pixels

/** Color palette constants for all board visual elements. */
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

/**
 * Main Board component — renders the full SVG game board.
 *
 * @param {object}   gameState      — Current game state from the server.
 * @param {number[]} selectedPiece  — [y, x] of the selected piece, or null.
 * @param {number[][]} validMoves   — List of [y, x] valid move destinations.
 * @param {number[][]} validPushDirs — List of [dy, dx] push direction vectors.
 * @param {object}   pendingAiAction — Current AI action being animated.
 * @param {function} onCellClick    — Handler for cell clicks.
 * @param {function} onPushDir      — Handler for push direction clicks.
 * @param {boolean}  setupMode      — Whether the game is in setup phase.
 * @param {string}   setupPlayer    — Current player placing pieces in setup.
 */
export function Board({
  gameState, selectedPiece, validMoves, validPushDirs,
  pendingAiAction, onCellClick, onPushDir,
  setupMode, setupPlayer,
}) {
  const W = 10 * CELL           // Board width (10 columns after transposition)
  const H = 4 * CELL            // Board height (4 rows after transposition)
  const GUTTER_LEFT = 20        // Space for column labels
  const GUTTER_TOP  = 20        // Space for row labels

  return (
    <svg
      width={W + GUTTER_LEFT} height={H + GUTTER_TOP}
      viewBox={`${-GUTTER_LEFT} ${-GUTTER_TOP} ${W + GUTTER_LEFT} ${H + GUTTER_TOP}`}
      style={{ display: 'block' }}
      role="application"
      aria-label="Push Fight board, landscape: 10 columns wide, 4 rows tall"
    >
      {/* Column labels A–D along the left edge (y-axis after transposing) */}
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

      {/* Row labels 1–10 along the top edge (x-axis after transposing) */}
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

      {/* Render all 10×4 board cells */}
      {gameState.board.map((row, y) =>
        row.map((cell, x) => {
          const isSel = selectedPiece?.[0] === y && selectedPiece?.[1] === x
          const isVM  = !cell.killZone && validMoves.some(([my, mx]) => my === y && mx === x)

          // Determine if this cell's piece is involved in a pending AI action
          const isAiSrc = pendingAiAction?.type === 'move'
            && pendingAiAction.from[0] === y && pendingAiAction.from[1] === x
          const isAiPusher = pendingAiAction?.type === 'push'
            && pendingAiAction.piece[0] === y && pendingAiAction.piece[1] === x
          const isAiHighlighted = isAiSrc || isAiPusher

          // During setup: highlight empty cells on the placing player's half
          const onSetupHalf = setupPlayer === 'white' ? y <= 4 : y >= 5
          const isSetupTarget = setupMode && onSetupHalf && !cell.killZone && !cell.piece

          return (
            <BoardCell
              key={`${y}-${x}`}
              cell={cell} y={y} x={x}
              isSelected={isSel}
              isValidMove={isVM}
              isAiHighlighted={isAiHighlighted}
              isSetupTarget={isSetupTarget}
              onCellClick={onCellClick}
            />
          )
        })
      )}

      {/* Centre line — vertical divider between rows 4 and 5 (after transposition) */}
      <line
        x1={5 * CELL} y1={0} x2={5 * CELL} y2={H}
        stroke={C.centerLine} strokeWidth={2} strokeDasharray="6 4"
        pointerEvents="none"
        aria-hidden="true"
      />

      {/* Push-direction arrows — appear at cell edges when a piece is selected */}
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
// BoardCell — individual cell with piece, overlays, and interaction
// ---------------------------------------------------------------------------

/** Column letter labels for coordinate display (A–D). */
const COL_LETTERS = ['A', 'B', 'C', 'D']

/** Format a cell coordinate as a human-readable string (e.g. "B3"). */
function cellCoord(y, x) {
  return `${COL_LETTERS[x]}${y + 1}`
}

/** Generate an ARIA label describing the cell's contents for screen readers. */
function cellAriaLabel(cell, y, x) {
  const coord = cellCoord(y, x)
  if (cell.killZone) return `Kill zone ${coord}`
  if (!cell.piece)   return `Empty cell ${coord}`
  const name   = cell.piece.name ? cell.piece.name.charAt(0).toUpperCase() + cell.piece.name.slice(1) : cell.piece.team
  const anchor = cell.isAnchor ? ', anchored' : ''
  return `${name} (${cell.piece.team})${anchor}, ${coord}`
}

/**
 * Renders a single board cell with its background, overlays, and piece.
 *
 * Visual states:
 *   - Kill zone: dark fill, non-interactive
 *   - Selected: gold border + yellow tint
 *   - AI highlighted: orange border + pulsing glow
 *   - Setup target: dashed green border
 *   - Valid move: blue dot overlay (when no piece occupies the cell)
 */
function BoardCell({ cell, y, x, isSelected, isValidMove, isAiHighlighted, isSetupTarget, onCellClick }) {
  const { killZone, piece, isAnchor } = cell

  // Determine cell background fill based on state priority
  const fill = killZone
    ? C.killZoneFill
    : isSelected
    ? 'rgba(255, 215, 0, 0.2)'
    : isSetupTarget
    ? 'rgba(100, 200, 120, 0.08)'
    : 'transparent'

  // Determine border color and width based on state
  const borderColor = isSelected
    ? C.selBorder
    : isAiHighlighted
    ? C.aiHighlight
    : isSetupTarget
    ? 'rgba(100, 200, 120, 0.5)'
    : 'rgba(0, 0, 0, 0.15)'
  const borderW = isSelected || isAiHighlighted ? 2.5 : isSetupTarget ? 1.5 : 1
  const strokeDash = isSetupTarget ? '4 3' : undefined

  /** Keyboard handler — Enter/Space triggers cell click for accessibility. */
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
      {/* Cell background rectangle — transposed: SVG x = game y, SVG y = game x */}
      <rect
        x={y * CELL + 1} y={x * CELL + 1}
        width={CELL - 2} height={CELL - 2}
        fill={fill}
        stroke={borderColor} strokeWidth={borderW}
        strokeDasharray={strokeDash}
        rx={3}
      />

      {/* AI pending-action glow effect (pulsing CSS animation) */}
      {isAiHighlighted && (
        <rect
          x={y * CELL + 1} y={x * CELL + 1}
          width={CELL - 2} height={CELL - 2}
          fill={C.aiHighlightGlow} rx={3}
          pointerEvents="none"
          style={{ animation: 'aiPulse 0.8s ease-in-out infinite alternate' }}
        />
      )}

      {/* Valid move indicator dot (shown on empty reachable cells) */}
      {isValidMove && !piece && (
        <circle
          cx={y * CELL + CELL / 2} cy={x * CELL + CELL / 2}
          r={11} fill={C.validMoveDot}
          pointerEvents="none"
          aria-hidden="true"
        />
      )}

      {/* Game piece (if present and not in a kill zone) */}
      {piece && !killZone && (
        <GamePiece piece={piece} x={x} y={y} isAnchor={isAnchor} />
      )}
    </g>
  )
}

// ---------------------------------------------------------------------------
// GamePiece — SVG rendering of a single piece with label and anchor
// ---------------------------------------------------------------------------

/**
 * Renders a game piece as either a rounded rectangle (square piece)
 * or a circle (round piece), with the BJJ name label and optional
 * anchor marker (gold dot).
 */
function GamePiece({ piece, x, y, isAnchor }) {
  const isWhite = piece.team === 'white'
  const fill    = isWhite ? C.pieceWhite    : C.pieceBlack
  const stroke  = isWhite ? C.pieceWhiteStroke : C.pieceBlackStroke
  const pad     = 9                          // Padding from cell edges
  const cx      = y * CELL + CELL / 2       // Center X (transposed: game row → SVG x)
  const cy      = x * CELL + CELL / 2       // Center Y (transposed: game col → SVG y)
  const size    = CELL - pad * 2             // Piece dimensions
  const label   = piece.name ? piece.name : (isWhite ? 'W' : 'B')
  const pieceName = piece.name ? piece.name.charAt(0).toUpperCase() + piece.name.slice(1) : (isWhite ? 'White' : 'Black')

  return (
    <g pointerEvents="none" aria-hidden="true">
      <title>{pieceName} ({piece.team}) — {cellCoord(y, x)}</title>

      {/* Piece shape: rounded rect for square, circle for round */}
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

      {/* Piece name label (lowercase, centered) */}
      <text
        x={cx} y={cy + 1}
        textAnchor="middle" dominantBaseline="middle"
        fontSize={8} fontWeight="bold" fontFamily="system-ui, sans-serif"
        fill={isWhite ? '#7a5a28' : '#c89060'}
        className={`piece-label ${isWhite ? 'piece-label-white' : 'piece-label-black'}`}
      >
        {label}
      </text>

      {/* Anchor marker: gold dot with dark shadow ring */}
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
// PushArrow — clickable directional arrow at the edge of a selected cell
// ---------------------------------------------------------------------------

/**
 * Renders a triangular push-direction arrow with an invisible hit area.
 *
 * Positioned at the edge of the selected piece's cell, pointing in the
 * push direction.  Accounts for the board's coordinate transposition:
 *   - dy changes map to left/right visually (SVG x-axis)
 *   - dx changes map to up/down visually (SVG y-axis)
 *
 * @param {number} py, px — Position of the pushing piece (game coords).
 * @param {number} dy, dx — Push direction unit vector.
 * @param {function} onPushDir — Callback when the arrow is clicked.
 */
function PushArrow({ py, px, dy, dx, onPushDir }) {
  const MARGIN = 9   // Distance from cell edge to arrow tip
  const S      = 12  // Arrow triangle size

  // Compute the arrow tip position in SVG coordinates (transposed)
  const svgCX = py * CELL + CELL / 2
  const svgCY = px * CELL + CELL / 2
  let tipX, tipY

  // dy=-1 (game row decreases) → visual left (SVG x decreases)
  if      (dy === -1) { tipX = py * CELL + MARGIN;        tipY = svgCY }
  // dy=+1 (game row increases) → visual right (SVG x increases)
  else if (dy ===  1) { tipX = py * CELL + CELL - MARGIN; tipY = svgCY }
  // dx=-1 (game col decreases) → visual up (SVG y decreases)
  else if (dx === -1) { tipX = svgCX;                     tipY = px * CELL + MARGIN }
  // dx=+1 (game col increases) → visual down (SVG y increases)
  else                { tipX = svgCX;                     tipY = px * CELL + CELL - MARGIN }

  // Build the triangular arrow polygon pointing in the push direction
  const pts = [
    [tipX,                          tipY                         ],
    [tipX - dy * S - dx * S * 0.6, tipY - dx * S + dy * S * 0.6],
    [tipX - dy * S + dx * S * 0.6, tipY - dx * S - dy * S * 0.6],
  ].map(([a, b]) => `${a.toFixed(1)},${b.toFixed(1)}`).join(' ')

  // Invisible hit area rectangle covering half the cell in the push direction
  const HIT = CELL / 2
  const hx  = dy === -1 ? py * CELL : dy === 1 ? py * CELL + HIT : py * CELL + CELL / 4
  const hy  = dx === -1 ? px * CELL : dx === 1 ? px * CELL + HIT : px * CELL + CELL / 4
  const hw  = dy !== 0 ? HIT : CELL / 2
  const hh  = dx !== 0 ? HIT : CELL / 2

  // Human-readable direction label for ARIA accessibility
  const dirLabel = dy === -1 ? 'left' : dy === 1 ? 'right' : dx === -1 ? 'up' : 'down'

  return (
    <g
      onClick={(e) => { e.stopPropagation(); onPushDir(dy, dx) }}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPushDir(dy, dx) } }}
      tabIndex={0}
      role="button"
      aria-label={`Push ${dirLabel}`}
      style={{ cursor: 'pointer', outline: 'none' }}
    >
      {/* Invisible hit area for easier clicking */}
      <rect x={hx} y={hy} width={hw} height={hh} fill="transparent" />
      {/* Glow circle behind the arrow */}
      <circle cx={tipX} cy={tipY} r={15} fill={C.pushArrowGlow} />
      {/* Arrow triangle */}
      <polygon points={pts} fill={C.pushArrow} stroke="#ffaa60" strokeWidth={1} />
    </g>
  )
}
