/**
 * TutorialModal — Interactive "How to Play" tutorial with slide-based navigation.
 *
 * Presents 9 illustrated slides that teach the complete rules of Push Fight:
 *   1. Welcome & overview
 *   2. Board layout (10×4 grid, kill zones, center line)
 *   3. Piece types (3 square pushers + 2 round non-pushers)
 *   4. Setup phase (placing pieces on your half)
 *   5. Move phase (slide pieces via BFS pathfinding)
 *   6. Push phase (mandatory push with chain mechanics)
 *   7. Anchor rule (blocks opponent's push chains)
 *   8. Win conditions (1 round OR 2 squares eliminated)
 *   9. Strategy tips
 *
 * Each slide uses mini SVG board diagrams (MiniBoard, MiniPiece, MiniCell)
 * to illustrate concepts visually.  The mini boards share the same grid
 * layout as the actual game board but use smaller cells (28px vs 64px).
 *
 * Navigation: arrow buttons, keyboard arrows, Escape to close.
 */

import { useState } from 'react'

/** Color palette matching the main Board.jsx component. */
const C = {
  boardBg:     '#5d4037',
  killZone:    'rgba(0,0,0,0.38)',
  cellStroke:  'rgba(255,255,255,0.08)',
  centerLine:  'rgba(255,215,0,0.35)',
  pieceWhite:  '#f0e8d8',
  strokeWhite: '#b89a60',
  pieceBlack:  '#1e0e06',
  strokeBlack: '#6a3818',
  anchor:      '#ffd700',
  pushArrow:   '#ff6b1a',
  validMove:   'rgba(0, 85, 212, 0.65)',
  setupTarget: 'rgba(100, 200, 120, 0.5)',
}

/** Board grid layout: 0 = playable, -1 = kill zone. */
const GRID = [
  [-1, -1, -1, -1],
  [-1,  0,  0, -1],
  [ 0,  0,  0, -1],
  [ 0,  0,  0,  0],
  [ 0,  0,  0,  0],
  [ 0,  0,  0,  0],
  [ 0,  0,  0,  0],
  [-1,  0,  0,  0],
  [-1,  0,  0, -1],
  [-1, -1, -1, -1],
]

const S = 28    // Cell size for mini diagrams (pixels)
const PAD = 2   // Padding around the mini board

// ---------------------------------------------------------------------------
// Mini board helper components (used in slide illustrations)
// ---------------------------------------------------------------------------

/** Renders a single cell in the mini board diagram. */
function MiniCell({ row, col }) {
  const isKill = GRID[row][col] === -1
  const x = col * S + PAD
  const y = row * S + PAD
  return (
    <rect
      x={x} y={y} width={S} height={S}
      fill={isKill ? C.killZone : C.boardBg}
      stroke={C.cellStroke}
      strokeWidth={0.5}
    />
  )
}

/** Renders a piece in the mini board: square or circle with optional label and anchor. */
function MiniPiece({ row, col, shape, team, label, showAnchor }) {
  const cx = col * S + PAD + S / 2
  const cy = row * S + PAD + S / 2
  const fill   = team === 'white' ? C.pieceWhite  : C.pieceBlack
  const stroke = team === 'white' ? C.strokeWhite : C.strokeBlack
  const textFill = team === 'white' ? '#333' : '#ddd'
  const r = S * 0.38

  return (
    <g>
      {shape === 'square' ? (
        <rect
          x={cx - r} y={cy - r} width={r * 2} height={r * 2}
          fill={fill} stroke={stroke} strokeWidth={1.5} rx={3}
        />
      ) : (
        <circle cx={cx} cy={cy} r={r}
          fill={fill} stroke={stroke} strokeWidth={1.5}
        />
      )}
      {label && (
        <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central"
          fontSize={6} fontWeight={700} fill={textFill} style={{ pointerEvents: 'none' }}>
          {label}
        </text>
      )}
      {showAnchor && (
        <circle cx={cx} cy={cy - r + 3} r={2.5}
          fill={C.anchor} stroke="none"
        />
      )}
    </g>
  )
}

/** Wrapper SVG that renders the full mini board grid with child overlays. */
function MiniBoard({ children, width, height }) {
  return (
    <svg width={width || (4 * S + PAD * 2)} height={height || (10 * S + PAD * 2)}
      style={{ display: 'block', margin: '12px auto' }}
      aria-hidden="true">
      {GRID.map((row, r) =>
        row.map((_, c) => <MiniCell key={`${r}-${c}`} row={r} col={c} />)
      )}
      {children}
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Slide content components — each renders one tutorial page
// ---------------------------------------------------------------------------

/** Slide 1: Introduction to Push Fight. */
function WelcomeSlide() {
  return (
    <>
      <p>
        <strong>Push Fight</strong> is a two-player abstract strategy game.
        Your goal: push your opponent's pieces off the edge of the board.
      </p>
      <p>
        Each turn you get up to <strong>2 moves</strong> followed by
        a mandatory <strong>push</strong>. Outmaneuver your opponent by
        controlling the center and protecting your vulnerable pieces.
      </p>
      <p>
        The pieces are themed after BJJ (Brazilian Jiu-Jitsu) — you'll see
        names like <strong>sleeve</strong>, <strong>lapel</strong>, and <strong>belt</strong>.
      </p>
    </>
  )
}

/** Slide 2: Board layout with kill zones and center line. */
function BoardSlide() {
  const w = 4 * S + PAD * 2
  return (
    <>
      <p>
        The board is a <strong>10 × 4 grid</strong> with an irregular shape.
        The dark cells at the edges are <strong>kill zones</strong> — pieces pushed
        there are eliminated.
      </p>
      <MiniBoard>
        {/* Center line divider */}
        <line
          x1={PAD} y1={5 * S + PAD}
          x2={4 * S + PAD} y2={5 * S + PAD}
          stroke={C.centerLine} strokeWidth={1.5} strokeDasharray="4 3"
        />
        {/* Zone labels */}
        <text x={w / 2} y={S * 0.5 + PAD} textAnchor="middle"
          fontSize={7} fill="#ff8888" fontWeight={600}>Kill Zone</text>
        <text x={w / 2} y={S * 3 + PAD} textAnchor="middle"
          fontSize={7} fill="#ccc" fontWeight={500}>White's half</text>
        <text x={w / 2} y={S * 7 + PAD} textAnchor="middle"
          fontSize={7} fill="#ccc" fontWeight={500}>Black's half</text>
        <text x={w / 2} y={S * 9.5 + PAD} textAnchor="middle"
          fontSize={7} fill="#ff8888" fontWeight={600}>Kill Zone</text>
      </MiniBoard>
      <p>
        Each player starts on their own half. The dashed line marks the center.
      </p>
    </>
  )
}

/** Slide 3: Piece types — square pushers vs round non-pushers. */
function PieceTypesSlide() {
  return (
    <>
      <p>
        Each team has <strong>5 pieces</strong> — 3 square and 2 round.
      </p>
      <div className="tutorial-pieces-row">
        {/* Square pieces (can push) */}
        {[
          { name: 'sleeve', shape: 'square' },
          { name: 'lapel',  shape: 'square' },
          { name: 'belt',   shape: 'square' },
        ].map(p => (
          <div key={p.name} className="tutorial-piece-item">
            <svg width={36} height={36} aria-hidden="true">
              {p.shape === 'square' ? (
                <rect x={4} y={4} width={28} height={28} rx={4}
                  fill={C.pieceWhite} stroke={C.strokeWhite} strokeWidth={2} />
              ) : (
                <circle cx={18} cy={18} r={14}
                  fill={C.pieceWhite} stroke={C.strokeWhite} strokeWidth={2} />
              )}
              <text x={18} y={18} textAnchor="middle" dominantBaseline="central"
                fontSize={8} fontWeight={700} fill="#333">{p.name}</text>
            </svg>
            <span className="tutorial-piece-label tutorial-piece-label--push">Can push</span>
          </div>
        ))}
        {/* Round pieces (cannot push) */}
        {[
          { name: 'neck',  shape: 'circle' },
          { name: 'joint', shape: 'circle' },
        ].map(p => (
          <div key={p.name} className="tutorial-piece-item">
            <svg width={36} height={36} aria-hidden="true">
              <circle cx={18} cy={18} r={14}
                fill={C.pieceWhite} stroke={C.strokeWhite} strokeWidth={2} />
              <text x={18} y={18} textAnchor="middle" dominantBaseline="central"
                fontSize={8} fontWeight={700} fill="#333">{p.name}</text>
            </svg>
            <span className="tutorial-piece-label tutorial-piece-label--no-push">Cannot push</span>
          </div>
        ))}
      </div>
      <p>
        <strong>Square pieces</strong> (sleeve, lapel, belt) are the only ones that
        can initiate a push. <strong>Round pieces</strong> (neck, joint) can move
        but cannot push.
      </p>
    </>
  )
}

/** Slide 4: Setup phase — placing pieces on your half. */
function SetupSlide() {
  return (
    <>
      <p>
        At the start, each player takes turns placing their <strong>5 pieces</strong> on
        their half of the board. Tap a piece in the tray, then click a highlighted cell.
      </p>
      <MiniBoard>
        {/* Highlight valid setup cells on white's half */}
        {[[1,1],[1,2],[2,0],[2,1],[2,2],[3,0],[3,1],[3,2],[3,3],[4,0],[4,1],[4,2],[4,3]].map(([r,c]) => (
          <rect key={`s-${r}-${c}`}
            x={c * S + PAD + 2} y={r * S + PAD + 2}
            width={S - 4} height={S - 4}
            fill="rgba(100, 200, 120, 0.08)"
            stroke={C.setupTarget}
            strokeWidth={1} strokeDasharray="3 2" rx={2}
          />
        ))}
        {/* Example placed pieces */}
        <MiniPiece row={3} col={1} shape="square" team="white" label="slv" />
        <MiniPiece row={4} col={2} shape="circle" team="white" label="nck" />
      </MiniBoard>
      <p>
        Once all pieces are placed, confirm your setup. Then the game begins!
      </p>
    </>
  )
}

/** Slide 5: Move phase — selecting and sliding pieces. */
function MoveSlide() {
  return (
    <>
      <p>
        On your turn, you can make up to <strong>2 moves</strong>. Click a piece
        to select it, then click a blue dot to slide it there.
      </p>
      <MiniBoard>
        {/* Selected piece with gold border */}
        <MiniPiece row={4} col={1} shape="square" team="white" label="slv" />
        <rect x={1 * S + PAD + 1} y={4 * S + PAD + 1}
          width={S - 2} height={S - 2}
          fill="none" stroke={C.anchor} strokeWidth={1.5} rx={2} />
        {/* Valid move destination dots */}
        {[[3,1],[4,0],[4,2],[5,1]].map(([r,c]) => (
          <circle key={`vm-${r}-${c}`}
            cx={c * S + PAD + S / 2}
            cy={r * S + PAD + S / 2}
            r={4} fill={C.validMove}
          />
        ))}
        {/* Context pieces */}
        <MiniPiece row={3} col={2} shape="square" team="white" label="lpl" />
        <MiniPiece row={4} col={3} shape="circle" team="white" label="nck" />
        <MiniPiece row={6} col={1} shape="square" team="black" label="slv" />
        <MiniPiece row={5} col={2} shape="circle" team="black" label="nck" />
      </MiniBoard>
      <p>
        Pieces slide to any reachable empty space (connected path, no diagonals).
        You can also <strong>skip remaining moves</strong> to go straight to the push.
      </p>
    </>
  )
}

/** Slide 6: Push phase — chain push mechanics. */
function PushSlide() {
  return (
    <>
      <p>
        After moving, you <strong>must push</strong>. Select one of your
        square pieces & choose a direction. The push shoves the entire line of pieces.
      </p>
      <svg width={4 * S + PAD * 2} height={3 * S + PAD * 2 + 10}
        style={{ display: 'block', margin: '12px auto' }} aria-hidden="true">
        {/* 3-row strip showing a push chain */}
        {[0,1,2].map(r => [0,1,2,3].map(c => (
          <rect key={`${r}-${c}`}
            x={c * S + PAD} y={r * S + PAD + 10}
            width={S} height={S}
            fill={C.boardBg} stroke={C.cellStroke} strokeWidth={0.5}
          />
        )))}
        {/* Pushing piece and chain target */}
        <MiniPiece row={0} col={0} shape="square" team="white" label="blt" />
        <MiniPiece row={0} col={1} shape="circle" team="black" label="nck" />
        {/* Arrow showing push direction (right) */}
        <g transform={`translate(${PAD},10)`}>
          <polygon
            points={`${S * 2 + S/2 + 6},${S/2} ${S * 2 + S/2 - 2},${S/2 - 6} ${S * 2 + S/2 - 2},${S/2 + 6}`}
            fill={C.pushArrow}
          />
          <line x1={0 * S + S} y1={S / 2} x2={S * 2 + S/2 - 2} y2={S / 2}
            stroke={C.pushArrow} strokeWidth={2} strokeDasharray="3 2" />
        </g>
        <text x={(4 * S + PAD * 2) / 2} y={S * 2 + PAD + 18}
          textAnchor="middle" fontSize={8} fill="#ccc">
          Belt pushes right → neck slides with it
        </text>
      </svg>
      <p>
        If a piece is pushed into a <strong>kill zone</strong>, it's eliminated.
        You can push multiple pieces in a chain!
      </p>
    </>
  )
}

/** Slide 7: Anchor rule — blocks opponent's push chains. */
function AnchorSlide() {
  return (
    <>
      <p>
        After you push, your pushing piece becomes the <strong>anchor</strong>,
        marked with a gold dot.
      </p>
      <svg width={4 * S + PAD * 2} height={2 * S + PAD * 2 + 8}
        style={{ display: 'block', margin: '12px auto' }} aria-hidden="true">
        {[0,1].map(r => [0,1,2,3].map(c => (
          <rect key={`${r}-${c}`}
            x={c * S + PAD} y={r * S + PAD}
            width={S} height={S}
            fill={C.boardBg} stroke={C.cellStroke} strokeWidth={0.5}
          />
        )))}
        <MiniPiece row={0} col={1} shape="square" team="white" label="slv" showAnchor />
        <MiniPiece row={0} col={2} shape="square" team="black" label="lpl" />
        {/* Blocked push indicator */}
        <g transform={`translate(${PAD},0)`}>
          <line x1={S * 3 + 4} y1={S / 2 + PAD} x2={S * 3 + 14} y2={S / 2 + PAD}
            stroke="#ff4444" strokeWidth={2} />
          <text x={S * 3 + 9} y={S / 2 + PAD - 6}
            textAnchor="middle" fontSize={9} fill="#ff4444" fontWeight={700}>✕</text>
        </g>
        <text x={(4 * S + PAD * 2) / 2} y={2 * S + PAD + 6}
          textAnchor="middle" fontSize={7} fill="#ccc">
          Anchor blocks opponent's push through it
        </text>
      </svg>
      <p>
        On the <strong>next turn</strong>, the anchor blocks push chains — your opponent
        cannot push through an anchored piece. The anchor moves to a new piece
        each time a push is made.
      </p>
    </>
  )
}

/** Slide 8: Win conditions. */
function WinSlide() {
  return (
    <>
      <p>
        You win by pushing your opponent's pieces into kill zones:
      </p>
      <ul>
        <li>Push off <strong>1 round piece</strong> (neck or joint) — instant win</li>
        <li>Push off <strong>2 square pieces</strong> (any combination) — win</li>
      </ul>
      <svg width={4 * S + PAD * 2} height={2 * S + PAD * 2}
        style={{ display: 'block', margin: '12px auto' }} aria-hidden="true">
        {/* Two rows: playable and kill zone */}
        <rect x={PAD} y={PAD} width={4 * S} height={S}
          fill={C.boardBg} stroke={C.cellStroke} strokeWidth={0.5} />
        <rect x={PAD} y={S + PAD} width={4 * S} height={S}
          fill={C.killZone} stroke={C.cellStroke} strokeWidth={0.5} />
        <text x={2 * S + PAD} y={S * 1.5 + PAD}
          textAnchor="middle" fontSize={7} fill="#ff8888" fontWeight={600}>Kill Zone</text>
        <MiniPiece row={0} col={2} shape="square" team="white" label="slv" />
        <MiniPiece row={0} col={1} shape="circle" team="black" label="nck" />
        {/* Arrow pointing into kill zone */}
        <polygon
          points={`${1 * S + PAD + S/2},${S + PAD + 3} ${1 * S + PAD + S/2 - 5},${S + PAD - 5} ${1 * S + PAD + S/2 + 5},${S + PAD - 5}`}
          fill={C.pushArrow}
        />
      </svg>
      <p>
        Protect your <strong>round pieces</strong> — losing even one means defeat!
      </p>
    </>
  )
}

/** Slide 9: Strategy tips and feature reminders. */
function TipsSlide() {
  return (
    <>
      <p>Now you're ready to play! Here are some tips:</p>
      <ul>
        <li>
          <strong>Protect your rounds</strong> — neck and joint are your most
          vulnerable pieces. Keep them away from edges.
        </li>
        <li>
          <strong>Use the anchor</strong> — after you push, your anchored piece
          blocks your opponent. Place it strategically.
        </li>
        <li>
          <strong>Control the center</strong> — pieces near the edges are easier
          to push off. Fight for central board position.
        </li>
        <li>
          <strong>Skip moves wisely</strong> — sometimes pushing immediately
          is stronger than using both moves.
        </li>
        <li>
          <strong>Think in chains</strong> — a single push can move multiple
          pieces at once. Set up chain pushes for maximum impact.
        </li>
      </ul>
      <div className="tutorial-tip">
        You can also use <strong>voice commands</strong> (click "Mic On") or
        ask the <strong>referee</strong> for rule clarifications during the game.
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Slide definitions — ordered array of { title, content } objects
// ---------------------------------------------------------------------------

const SLIDES = [
  { title: 'Welcome to Push Fight',  content: <WelcomeSlide /> },
  { title: 'The Board',              content: <BoardSlide /> },
  { title: 'Piece Types',            content: <PieceTypesSlide /> },
  { title: 'Setup Phase',            content: <SetupSlide /> },
  { title: 'Move Phase',             content: <MoveSlide /> },
  { title: 'Push Phase',             content: <PushSlide /> },
  { title: 'The Anchor',             content: <AnchorSlide /> },
  { title: 'Winning the Game',       content: <WinSlide /> },
  { title: 'Tips & Strategy',        content: <TipsSlide /> },
]

// ---------------------------------------------------------------------------
// TutorialModal — main exported component
// ---------------------------------------------------------------------------

/**
 * Modal dialog with slide-based navigation for learning Push Fight rules.
 *
 * Supports keyboard navigation: ArrowLeft/Right to navigate, Escape to close.
 *
 * @param {function} onClose — Callback to close the tutorial modal.
 */
export function TutorialModal({ onClose }) {
  const [slideIndex, setSlideIndex] = useState(0)

  const next = () => setSlideIndex(i => Math.min(i + 1, SLIDES.length - 1))
  const prev = () => setSlideIndex(i => Math.max(i - 1, 0))

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose()
    else if (e.key === 'ArrowRight') next()
    else if (e.key === 'ArrowLeft') prev()
  }

  const isLast = slideIndex === SLIDES.length - 1

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-label="How to Play Push Fight"
    >
      <div className="modal tutorial-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{SLIDES[slideIndex].title}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close dialog">✕</button>
        </div>

        <div className="modal-body tutorial-body">
          {SLIDES[slideIndex].content}
        </div>

        <div className="modal-footer tutorial-footer">
          {/* Slide progress indicator */}
          <span className="tutorial-progress">
            {slideIndex + 1} / {SLIDES.length}
          </span>
          <div className="tutorial-nav">
            <button
              className="btn btn-ghost btn-small"
              onClick={prev}
              disabled={slideIndex === 0}
            >
              ← Back
            </button>
            {isLast ? (
              <button className="btn btn-primary btn-small" onClick={onClose}>
                Got it!
              </button>
            ) : (
              <button className="btn btn-primary btn-small" onClick={next}>
                Next →
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
