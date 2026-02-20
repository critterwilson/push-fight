/**
 * Tests for the Board SVG component (frontend/src/Board.jsx).
 *
 * The Board component renders the 10x4 Push Fight grid as an SVG element
 * with interactive cells, pieces (showing names or team-letter fallbacks),
 * kill-zone indicators, valid-move dots, push-direction arrows, coordinate
 * labels (A-D columns, 1-10 rows), and accessibility attributes.
 *
 * Testing strategy:
 *   - Renders the Board with controlled props using @testing-library/react.
 *   - Fixture helpers (makeBoard, makeGameState) create realistic game state
 *     objects with optional piece overrides, matching the serialized format
 *     sent by the server.
 *   - Tests verify: SVG rendering, accessibility labels (role + aria-label),
 *     cell count, click handlers, kill-zone click suppression, valid-move
 *     indicators, push arrow rendering, piece name labels, coordinate labels,
 *     and aria-label coordinate notation.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Board } from '../Board'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/**
 * Build a 10x4 board grid matching the server's serialized format.
 * Each cell has y, x, killZone, piece, and isAnchor fields.
 * The piecesOverride map uses "y,x" keys to inject specific pieces.
 */
function makeBoard(piecesOverride = {}) {
  return Array.from({ length: 10 }, (_, y) =>
    Array.from({ length: 4 }, (_, x) => {
      const key = `${y},${x}`
      return {
        y, x,
        killZone: (y === 0 || y === 9) ||
                  (y === 1 && (x === 0 || x === 3)) ||
                  (y === 2 && x === 3) ||
                  (y === 7 && x === 0) ||
                  (y === 8 && (x === 0 || x === 3)),
        piece: piecesOverride[key] ?? null,
        isAnchor: false,
      }
    })
  )
}

/**
 * Build a minimal game state object with sensible defaults.
 * The overrides parameter can inject custom pieces (via overrides.pieces),
 * change the current player, game phase flags, etc.
 */
function makeGameState(overrides = {}) {
  return {
    board: makeBoard(overrides.pieces),
    currentPlayer: 'white',
    canMove: true,
    canPush: false,
    gameOver: false,
    isAiTurn: false,
    ...overrides,
  }
}

/** Default props for the Board component — empty board, no selection,
 *  no valid moves/pushes, with vi.fn() spies on callbacks. */
const DEFAULT_PROPS = {
  gameState: makeGameState(),
  selectedPiece: null,
  validMoves: [],
  validPushDirs: [],
  pendingAiAction: null,
  onCellClick: vi.fn(),
  onPushDir: vi.fn(),
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Board', () => {
  // ── Basic rendering ─────────────────────────────────────────────────────

  it('renders an SVG element', () => {
    /** The Board must render as an SVG (not HTML table or canvas) for
     *  scalable, resolution-independent board graphics. */
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    expect(container.querySelector('svg')).toBeTruthy()
  })

  it('SVG has accessible role and label', () => {
    /** The root SVG element must have role="application" and a descriptive
     *  aria-label so screen readers announce the board context. */
    render(<Board {...DEFAULT_PROPS} />)
    expect(screen.getByRole('application')).toHaveAttribute(
      'aria-label',
      'Push Fight board, landscape: 10 columns wide, 4 rows tall',
    )
  })

  it('renders 40 cells (10 rows × 4 cols)', () => {
    /** Every cell of the 10x4 grid must be present in the DOM, identified
     *  by data-row attributes. This ensures the full board is rendered. */
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    const cells = container.querySelectorAll('[data-row]')
    expect(cells).toHaveLength(40)
  })

  // ── Click handling ──────────────────────────────────────────────────────

  it('calls onCellClick with correct (y, x) when a playable cell is clicked', () => {
    /** Clicking a playable cell must invoke onCellClick with the cell's
     *  (y, x) coordinates so the game hook can process piece selection
     *  or movement. */
    const onCellClick = vi.fn()
    const { container } = render(
      <Board {...DEFAULT_PROPS} onCellClick={onCellClick} />
    )
    // Row 3, col 0 is always a playable cell
    const cell = container.querySelector('[data-row="3"][data-col="0"]')
    fireEvent.click(cell)
    expect(onCellClick).toHaveBeenCalledWith(3, 0)
  })

  it('does not call onCellClick when a kill-zone cell is clicked', () => {
    /** Kill-zone cells are not interactive — clicks on them must be
     *  suppressed. This prevents accidental piece placement or movement
     *  into death zones. */
    const onCellClick = vi.fn()
    const { container } = render(
      <Board {...DEFAULT_PROPS} onCellClick={onCellClick} />
    )
    // Row 0 is always a kill zone
    const cell = container.querySelector('[data-row="0"][data-col="0"]')
    fireEvent.click(cell)
    expect(onCellClick).not.toHaveBeenCalled()
  })

  // ── Valid-move indicators ───────────────────────────────────────────────

  it('renders a valid-move indicator (circle) when validMoves contains the cell', () => {
    /** When a piece is selected, valid destination cells should display a
     *  small circle indicator so the player knows where they can move. */
    const { container } = render(
      <Board {...DEFAULT_PROPS} validMoves={[[3, 0]]} />
    )
    const cell = container.querySelector('[data-row="3"][data-col="0"]')
    expect(cell.querySelector('circle')).toBeTruthy()
  })

  // ── Push arrows ─────────────────────────────────────────────────────────

  it('renders push arrows when selectedPiece and validPushDirs are set', () => {
    /** When a square piece is selected for pushing, directional arrow
     *  buttons must appear for each valid push direction. */
    const { container } = render(
      <Board
        {...DEFAULT_PROPS}
        selectedPiece={[4, 0]}
        validPushDirs={[[-1, 0], [0, 1]]}
      />
    )
    const arrows = screen.getAllByRole('button', { name: /push/i })
    expect(arrows).toHaveLength(2)
  })

  it('push arrow calls onPushDir with correct direction on click', () => {
    /** Clicking a push arrow must invoke onPushDir with the direction
     *  vector (dy, dx). Note: the board is transposed so dy=-1 maps to
     *  visual "left" on screen. */
    const onPushDir = vi.fn()
    render(
      <Board
        {...DEFAULT_PROPS}
        selectedPiece={[4, 0]}
        validPushDirs={[[-1, 0]]}
        onPushDir={onPushDir}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /push left/i }))
    expect(onPushDir).toHaveBeenCalledWith(-1, 0)
  })

  // ── Piece rendering ─────────────────────────────────────────────────────

  it('renders pieces without names using W/B team-letter fallback', () => {
    /** Pieces that lack a name field (e.g., from old save files) must
     *  fall back to displaying "W" or "B" based on team color. */
    const pieces = {
      '4,0': { team: 'white', shape: 'square' },
      '5,0': { team: 'black', shape: 'round'  },
    }
    const { container } = render(
      <Board {...DEFAULT_PROPS} gameState={makeGameState({ pieces })} />
    )
    const texts = [...container.querySelectorAll('text')].map(t => t.textContent)
    expect(texts).toContain('W')
    expect(texts).toContain('B')
  })

  // ── Selection state ─────────────────────────────────────────────────────

  it('selected cell has aria-pressed="true"', () => {
    /** The currently selected cell must have aria-pressed="true" for
     *  screen reader users to know which piece is active. */
    const { container } = render(
      <Board {...DEFAULT_PROPS} selectedPiece={[4, 1]} />
    )
    const cell = container.querySelector('[data-row="4"][data-col="1"]')
    expect(cell).toHaveAttribute('aria-pressed', 'true')
  })

  // ── Coordinate labels (voice-control feature) ────────────────────────────

  it('renders column labels A, B, C, D', () => {
    /** Column labels are rendered alongside the board so players can use
     *  voice commands with coordinate notation (e.g., "sleeve to B4"). */
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    const texts = [...container.querySelectorAll('text')].map(t => t.textContent)
    expect(texts).toContain('A')
    expect(texts).toContain('B')
    expect(texts).toContain('C')
    expect(texts).toContain('D')
  })

  it('renders row labels 1 through 10', () => {
    /** All 10 row labels must be rendered for complete coordinate reference. */
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    const texts = [...container.querySelectorAll('text')].map(t => t.textContent)
    for (let i = 1; i <= 10; i++) {
      expect(texts).toContain(String(i))
    }
  })

  // ── Piece name labels (voice-control feature) ───────────────────────────

  it('piece with name shows full name, not team letter', () => {
    /** When pieces have BJJ names (sleeve, lapel, belt, neck, joint), the
     *  Board must render the full name as the label text. Team-letter
     *  fallbacks (W/B) must NOT appear for named pieces. */
    const pieces = {
      '4,0': { team: 'white', shape: 'square', name: 'sleeve' },
      '4,1': { team: 'white', shape: 'square', name: 'lapel'  },
      '4,2': { team: 'white', shape: 'square', name: 'belt'   },
      '4,3': { team: 'white', shape: 'round',  name: 'neck'   },
      '3,1': { team: 'white', shape: 'round',  name: 'joint'  },
    }
    const { container } = render(
      <Board {...DEFAULT_PROPS} gameState={makeGameState({ pieces })} />
    )
    const texts = [...container.querySelectorAll('text')].map(t => t.textContent)
    expect(texts).toContain('sleeve')
    expect(texts).toContain('lapel')
    expect(texts).toContain('belt')
    expect(texts).toContain('neck')
    expect(texts).toContain('joint')
    // Team letters should NOT appear for named pieces
    expect(texts).not.toContain('W')
  })

  // ── Updated aria-labels (coordinate notation) ───────────────────────────

  it('empty cell aria-label uses coordinate notation', () => {
    /** Empty playable cells must have an aria-label like "A4, empty" using
     *  the column-letter + row-number coordinate system. */
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    // Row 3 (y=3), col 0 (x=0) → coordinate A4 (1-indexed row)
    const cell = container.querySelector('[data-row="3"][data-col="0"]')
    expect(cell.getAttribute('aria-label')).toMatch(/A4/i)
  })

  it('kill zone aria-label uses coordinate notation', () => {
    /** Kill-zone cells must include the coordinate in their aria-label so
     *  screen reader users can identify the danger zones spatially. */
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    // Row 0, col 0 → kill zone A1
    const cell = container.querySelector('[data-row="0"][data-col="0"]')
    expect(cell.getAttribute('aria-label')).toMatch(/A1/i)
  })

  it('piece aria-label includes piece name and coordinate', () => {
    /** Cells containing named pieces must have an aria-label that includes
     *  both the piece name and coordinate for full accessibility context. */
    const pieces = {
      '4,0': { team: 'white', shape: 'square', name: 'sleeve' },
    }
    const { container } = render(
      <Board {...DEFAULT_PROPS} gameState={makeGameState({ pieces })} />
    )
    // Row 4 (y=4), col 0 (x=0) → coordinate A5
    const cell = container.querySelector('[data-row="4"][data-col="0"]')
    const label = cell.getAttribute('aria-label')
    expect(label).toMatch(/sleeve/i)
    expect(label).toMatch(/A5/i)
  })

  it('piece aria-label falls back gracefully when piece has no name', () => {
    /** Pieces without a name field (legacy saves) must still have an
     *  aria-label containing the coordinate — no crash or empty label. */
    const pieces = {
      '4,0': { team: 'white', shape: 'square' },
    }
    const { container } = render(
      <Board {...DEFAULT_PROPS} gameState={makeGameState({ pieces })} />
    )
    const cell = container.querySelector('[data-row="4"][data-col="0"]')
    expect(cell.getAttribute('aria-label')).toMatch(/A5/i)
  })
})
