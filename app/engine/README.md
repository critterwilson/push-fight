# Engine — Core Game Logic

Pure Python implementation of Push Fight. No I/O, no framework dependencies — just the rules.

## Files

| File | Purpose |
|------|---------|
| `pieces.py` | `Piece` dataclass — team, shape, BJJ name, serialization |
| `board.py` | `PushFightBoard` — grid definition, BFS movement, push chains, kill zones |
| `game_state.py` | `GameState` — turn flow, move/push execution, win conditions, setup mode |

---

## Board

The board is a **10×4 grid** stored in `board.grid`. Cells are either playable (`0`) or kill zones (`-1`):

```
Row  A    B    C    D
 0  [-1] [-1] [-1] [-1]   ← North kill zone
 1  [-1] [ 0] [ 0] [-1]
 2  [ 0] [ 0] [ 0] [-1]
 3  [ 0] [ 0] [ 0] [ 0]
 4  [ 0] [ 0] [ 0] [ 0]   ← White starts here (rows 0–4)
     ─── centre line ───
 5  [ 0] [ 0] [ 0] [ 0]   ← Black starts here (rows 5–9)
 6  [ 0] [ 0] [ 0] [ 0]
 7  [-1] [ 0] [ 0] [ 0]
 8  [-1] [ 0] [ 0] [-1]
 9  [-1] [-1] [-1] [-1]   ← South kill zone
```

The internal coordinate system is `(y=row, x=col)`. The frontend transposes this for landscape display — the engine coordinate system is never changed.

### Key methods

| Method | Description |
|--------|-------------|
| `get_valid_moves(y, x)` | BFS returning a **set** of reachable empty cells |
| `get_push_chain(y, x, dy, dx)` | Returns the list of pieces in a push line and the landing cell |
| `is_kill_zone(y, x)` | True if the cell is `-1` in the grid |
| `is_occupied(y, x)` | True if a `Piece` sits on that cell |

> **Important:** `get_valid_moves()` returns a `set`. Use `next(iter(valid))` not `valid[0]`.

---

## Pieces

Each `Piece` has three attributes:

| Attribute | Values |
|-----------|--------|
| `team` | `"white"` or `"black"` |
| `shape` | `"square"` or `"round"` |
| `name` | `"sleeve"`, `"lapel"`, `"belt"` (square) · `"neck"`, `"joint"` (round) |

Square pieces can push. Round pieces cannot. Losing a round piece is an instant loss; losing two square pieces is also a loss.

The BJJ names are stored in the engine and flow through `state_serializer.py` to the frontend — voice control and board labels both read from the same field.

---

## Game State

`GameState` owns a `PushFightBoard` and tracks all mutable turn state.

### Turn flow

```
start_of_turn
  │
  ├─ perform_move() × 0–2   (optional; BFS-validated)
  │
  └─ perform_push()          (mandatory; side-rail validated)
        │
        └─ switch_turn()     (raises if push not yet done)
```

### Anchor

After each push, `board.anchor_pos` is set to the pushing piece's new position. An anchored piece cannot be moved or pushed by the opponent on their next turn. The anchor clears when the anchored piece itself gets pushed off.

### Win conditions (checked inside `perform_push`)

- Opponent's round piece pushed off → instant win
- 2 of opponent's square pieces pushed off → win
- Opponent has no legal push at turn start → win (`has_legal_push()`)

### Setup mode

`GameState` supports an optional placement phase (`setup_mode=True`). `place_piece()` validates team side, shape limits (3 squares + 2 rounds), and kill-zone avoidance. Call `start_game()` to transition to normal play.

---

## Serialization

Both `PushFightBoard` and `GameState` implement `to_dict()` / `from_dict()` for JSON round-trips. `GameState` also exposes `save_to_file()` / `load_from_file()` for direct disk persistence.

The richer frontend serialization (camelCase, per-cell board array) lives in `app/server/state_serializer.py`.
