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
      'Push Fight board, 10 rows by 4 columns',
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

  it('renders pieces on the board', () => {
    const pieces = {
      '4,0': { team: 'white', shape: 'square' },
      '5,0': { team: 'black', shape: 'round'  },
    }
    const { container } = render(
      <Board {...DEFAULT_PROPS} gameState={makeGameState({ pieces })} />
    )
    // Two pieces should be rendered — look for the text labels W / B
    const texts = container.querySelectorAll('text')
    const labels = [...texts].map(t => t.textContent)
    expect(labels).toContain('W')
    expect(labels).toContain('B')
  })

  it('selected cell has aria-pressed="true"', () => {
    const { container } = render(
      <Board {...DEFAULT_PROPS} selectedPiece={[4, 1]} />
    )
    const cell = container.querySelector('[data-row="4"][data-col="1"]')
    expect(cell).toHaveAttribute('aria-pressed', 'true')
  })

  it('each playable cell has an accessible aria-label', () => {
    const { container } = render(<Board {...DEFAULT_PROPS} />)
    const playable = container.querySelector('[data-row="3"][data-col="0"]')
    expect(playable.getAttribute('aria-label')).toMatch(/row 4, column 1/i)
  })
})
