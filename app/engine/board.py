"""
Board representation for Push Fight: BJJ Edition.

The board is a 10-row × 4-column grid stored as a 2-D list.  Rows run
north–south (index 0 = north edge, index 9 = south edge) and columns
run west–east (index 0 = left, index 3 = right).

Grid cell values:
    0  — playable space
   -1  — kill zone / off-board (rows 0 & 9 fully, plus irregular corners)

The board has an irregular shape: not all corners are playable.  Kill
zones along the north and south edges are where pieces are eliminated
when pushed off the playable area.

Key concepts:
  - **Anchor**: After each push, a gold anchor marker is placed on the
    pushing square piece.  The opponent may not move or push the anchored
    piece on their next turn.
  - **Side rails**: Coordinates outside the 10×4 array act as impassable
    walls that block pushes entirely.

This module provides:
  - BFS-based movement reachability  (get_valid_moves)
  - Push-chain calculation           (get_push_chain)
  - Kill-zone detection              (is_kill_zone)
  - Full JSON serialization          (to_dict / from_dict)
"""

from typing import Any
from collections import deque


class PushFightBoard:
    """10×4 game board with irregular kill-zone boundaries.

    Attributes:
        grid:       2-D list encoding the board shape (0 = playable, -1 = kill zone).
        pieces:     2-D list of Piece objects (or None for empty cells).
        anchor_pos: (y, x) tuple marking the anchored piece, or (None, None).
    """

    # Cardinal movement directions (no diagonals allowed)
    DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # up, down, left, right

    def __init__(self, pieces=None):
        # Static board shape — defines which cells are playable (0) vs kill zone (-1).
        # The irregular corners (e.g. row 1 cols 0,3 and row 2 col 3) create the
        # distinctive Push Fight board silhouette.
        self.grid = [
            [-1, -1, -1, -1],  # Row 0: full north kill zone
            [-1,  0,  0, -1],  # Row 1: narrow corridor
            [ 0,  0,  0, -1],  # Row 2: wider, missing east corner
            [ 0,  0,  0,  0],  # Row 3: full width
            [ 0,  0,  0,  0],  # Row 4: white's home row (north of center)
            # ——— Center Line ———
            [ 0,  0,  0,  0],  # Row 5: black's home row (south of center)
            [ 0,  0,  0,  0],  # Row 6: full width
            [-1,  0,  0,  0],  # Row 7: wider, missing west corner
            [-1,  0,  0, -1],  # Row 8: narrow corridor
            [-1, -1, -1, -1],  # Row 9: full south kill zone
        ]

        # Piece placement grid — mirrors the board dimensions.
        # Each cell is either a Piece object or None.
        if pieces is None:
            self.pieces = [[None for _ in range(4)] for _ in range(10)]
        else:
            self.pieces = pieces

        # Anchor position tracks which piece last executed a push.
        # The anchored piece cannot be moved or used to push by the opponent.
        self.anchor_pos = (None, None)

    # ------------------------------------------------------------------
    # Coordinate queries
    # ------------------------------------------------------------------

    def is_on_board(self, y: int, x: int) -> bool:
        """Return True if (y, x) falls inside the 10×4 array bounds.

        Note: This does NOT check whether the cell is playable — kill-zone
        cells are still "on the board".  Coordinates entirely outside the
        array represent side rails (impassable walls).
        """
        return 0 <= y < 10 and 0 <= x < 4

    def get_piece(self, y: int, x: int):
        """Return the Piece at (y, x), None if empty, or 'OUT_OF_BOUNDS'.

        The sentinel string 'OUT_OF_BOUNDS' represents side-rail
        coordinates that lie outside the physical board.
        """
        if self.is_on_board(y, x):
            return self.pieces[y][x]
        return "OUT_OF_BOUNDS"

    def is_occupied(self, y: int, x: int) -> bool:
        """Return True if a game piece currently sits on this cell."""
        piece = self.get_piece(y, x)
        return piece is not None and piece != "OUT_OF_BOUNDS"

    def is_kill_zone(self, y: int, x: int) -> bool:
        """Return True if (y, x) is a kill-zone cell (grid value -1).

        Pieces pushed into a kill zone are removed from play and may
        trigger a win condition.
        """
        if self.is_on_board(y, x):
            return self.grid[y][x] == -1
        return False

    # ------------------------------------------------------------------
    # Movement & push logic
    # ------------------------------------------------------------------

    def get_valid_moves(self, start_y: int, start_x: int) -> set[Any]:
        """Compute all cells reachable from (start_y, start_x) via BFS.

        Movement rules:
          - Pieces slide orthogonally (no diagonals).
          - A piece can travel any distance along connected empty cells
            (like a rook that stops at obstacles).
          - Kill-zone cells and occupied cells block movement.

        Returns:
            A set of (y, x) tuples representing valid move destinations.
        """
        valid_destinations = set[Any]()
        visited = set()
        queue = deque([(start_y, start_x)])
        visited.add((start_y, start_x))

        while queue:
            curr_y, curr_x = queue.popleft()

            for dy, dx in self.DIRECTIONS:
                next_y, next_x = curr_y + dy, curr_x + dx

                # A neighboring cell is reachable if it:
                #   1. Has not been visited yet
                #   2. Falls within the 10×4 array bounds
                #   3. Is a playable space (grid value 0, not kill zone)
                #   4. Is not blocked by another piece
                if ((next_y, next_x) not in visited
                        and self.is_on_board(next_y, next_x)
                        and self.grid[next_y][next_x] == 0
                        and not self.is_occupied(next_y, next_x)):
                    valid_destinations.add((next_y, next_x))
                    visited.add((next_y, next_x))
                    queue.append((next_y, next_x))

        return valid_destinations

    def get_push_chain(self, start_y: int, start_x: int, dy: int, dx: int):
        """Build the chain of pieces that will be displaced by a push.

        Starting from the pushing square piece at (start_y, start_x),
        walk in direction (dy, dx) and collect every contiguous piece.
        The chain terminates when we reach an empty cell or the edge.

        Args:
            start_y, start_x: Position of the pushing piece.
            dy, dx:           Push direction unit vector (e.g. (1, 0) = south).

        Returns:
            (chain, landing_spot) where:
              - chain is a list of (y, x) positions of all linked pieces
              - landing_spot is the (y, x) just past the last piece,
                i.e. where the end piece would be displaced to.
        """
        chain = [(start_y, start_x)]

        # Walk along the push direction, collecting pieces
        curr_y, curr_x = start_y + dy, start_x + dx
        while self.is_on_board(curr_y, curr_x) and self.pieces[curr_y][curr_x] is not None:
            chain.append((curr_y, curr_x))
            curr_y += dy
            curr_x += dx

        return chain, (curr_y, curr_x)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the board to a JSON-compatible dictionary.

        Used for game saves and WebSocket state broadcasting.
        """
        pieces_serialized = []
        for row in self.pieces:
            row_serialized = []
            for piece in row:
                if piece is None:
                    row_serialized.append(None)
                else:
                    row_serialized.append(piece.to_dict())
            pieces_serialized.append(row_serialized)

        return {
            'grid': self.grid,
            'pieces': pieces_serialized,
            'anchor_pos': self.anchor_pos,
        }

    @staticmethod
    def from_dict(data: dict) -> "PushFightBoard":
        """Reconstruct a PushFightBoard from a serialized dictionary."""
        from .pieces import Piece

        board = PushFightBoard()
        board.grid = data['grid']

        # Rebuild the 2-D pieces array from serialized dicts
        pieces_deserialized = []
        for row in data['pieces']:
            row_deserialized = []
            for piece_data in row:
                if piece_data is None:
                    row_deserialized.append(None)
                else:
                    row_deserialized.append(Piece.from_dict(piece_data))
            pieces_deserialized.append(row_deserialized)

        board.pieces = pieces_deserialized
        board.anchor_pos = (
            tuple(data['anchor_pos'])
            if data['anchor_pos'][0] is not None
            else (None, None)
        )

        return board
