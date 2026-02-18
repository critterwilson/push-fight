import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Board } from '../Board'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

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
  it('renders an SVG element', () => {
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    expect(container.querySelector('svg')).toBeTruthy()
  })

  it('SVG has accessible role and label', () => {
    render(<Board {...DEFAULT_PROPS} />)
    expect(screen.getByRole('application')).toHaveAttribute(
      'aria-label',
      'Push Fight board, landscape: 10 columns wide, 4 rows tall',
    )
  })

  it('renders 40 cells (10 rows × 4 cols)', () => {
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    const cells = container.querySelectorAll('[data-row]')
    expect(cells).toHaveLength(40)
  })

  it('calls onCellClick with correct (y, x) when a playable cell is clicked', () => {
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
    const onCellClick = vi.fn()
    const { container } = render(
      <Board {...DEFAULT_PROPS} onCellClick={onCellClick} />
    )
    // Row 0 is always a kill zone
    const cell = container.querySelector('[data-row="0"][data-col="0"]')
    fireEvent.click(cell)
    expect(onCellClick).not.toHaveBeenCalled()
  })

  it('renders a valid-move indicator (circle) when validMoves contains the cell', () => {
    const { container } = render(
      <Board {...DEFAULT_PROPS} validMoves={[[3, 0]]} />
    )
    // The cell at (3,0) should contain a circle with the valid-move fill colour
    const cell = container.querySelector('[data-row="3"][data-col="0"]')
    expect(cell.querySelector('circle')).toBeTruthy()
  })

  it('renders push arrows when selectedPiece and validPushDirs are set', () => {
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
    const onPushDir = vi.fn()
    render(
      <Board
        {...DEFAULT_PROPS}
        selectedPiece={[4, 0]}
        validPushDirs={[[-1, 0]]}
        onPushDir={onPushDir}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /push up/i }))
    expect(onPushDir).toHaveBeenCalledWith(-1, 0)
  })

  it('renders pieces without names using W/B team-letter fallback', () => {
    const pieces = {
      '4,0': { team: 'white', shape: 'square' },
      '5,0': { team: 'black', shape: 'round'  },
    }
    const { container } = render(
      <Board {...DEFAULT_PROPS} gameState={makeGameState({ pieces })} />
    )
    // Pieces with no name field should fall back to 'W' / 'B'
    const texts = [...container.querySelectorAll('text')].map(t => t.textContent)
    expect(texts).toContain('W')
    expect(texts).toContain('B')
  })

  it('selected cell has aria-pressed="true"', () => {
    const { container } = render(
      <Board {...DEFAULT_PROPS} selectedPiece={[4, 1]} />
    )
    const cell = container.querySelector('[data-row="4"][data-col="1"]')
    expect(cell).toHaveAttribute('aria-pressed', 'true')
  })

  // ── Coordinate labels (voice-control feature) ────────────────────────────

  it('renders column labels A, B, C, D', () => {
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    const texts = [...container.querySelectorAll('text')].map(t => t.textContent)
    expect(texts).toContain('A')
    expect(texts).toContain('B')
    expect(texts).toContain('C')
    expect(texts).toContain('D')
  })

  it('renders row labels 1 through 10', () => {
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    const texts = [...container.querySelectorAll('text')].map(t => t.textContent)
    for (let i = 1; i <= 10; i++) {
      expect(texts).toContain(String(i))
    }
  })

  // ── Piece name labels (voice-control feature) ───────────────────────────

  it('piece with name shows full name, not team letter', () => {
    const pieces = {
      '4,0': { team: 'white', shape: 'square', name: 'sleeve' },
      '4,1': { team: 'white', shape: 'square', name: 'lapel'  },
      '4,2': { team: 'white', shape: 'square', name: 'belt'   },
      '4,3': { team: 'white', shape: 'round',  name: 'choke'  },
      '3,1': { team: 'white', shape: 'round',  name: 'lock'   },
    }
    const { container } = render(
      <Board {...DEFAULT_PROPS} gameState={makeGameState({ pieces })} />
    )
    const texts = [...container.querySelectorAll('text')].map(t => t.textContent)
    expect(texts).toContain('sleeve')
    expect(texts).toContain('lapel')
    expect(texts).toContain('belt')
    expect(texts).toContain('choke')
    expect(texts).toContain('lock')
    // Team letters should NOT appear for named pieces
    expect(texts).not.toContain('W')
  })

  // ── Updated aria-labels (coordinate notation) ───────────────────────────

  it('empty cell aria-label uses coordinate notation', () => {
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    // Row 3 (y=3), col 0 (x=0) → coordinate A4
    const cell = container.querySelector('[data-row="3"][data-col="0"]')
    expect(cell.getAttribute('aria-label')).toMatch(/A4/i)
  })

  it('kill zone aria-label uses coordinate notation', () => {
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    // Row 0, col 0 → kill zone A1
    const cell = container.querySelector('[data-row="0"][data-col="0"]')
    expect(cell.getAttribute('aria-label')).toMatch(/A1/i)
  })

  it('piece aria-label includes piece name and coordinate', () => {
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
    const pieces = {
      '4,0': { team: 'white', shape: 'square' },
    }
    const { container } = render(
      <Board {...DEFAULT_PROPS} gameState={makeGameState({ pieces })} />
    )
    const cell = container.querySelector('[data-row="4"][data-col="0"]')
    // Should still have an aria-label containing the coordinate
    expect(cell.getAttribute('aria-label')).toMatch(/A5/i)
  })
})
