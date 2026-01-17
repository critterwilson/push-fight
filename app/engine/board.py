from collections import deque


class PushFightBoard:
    def __init__(self, pieces = None):
        # 0 = Playable Space
        # -1 = Off-board/Kill Zone
        self.grid = [
            [-1, -1, -1, -1], # Row 0: North Kill Zone
            [-1,  0,  0, -1], # Row 1
            [ 0,  0,  0, -1], # Row 2
            [ 0,  0,  0,  0], # Row 3
            [ 0,  0,  0,  0], # Row 4 (White starts N of center)
            # --- Center Line ---
            [ 0,  0,  0,  0], # Row 5 (Brown starts S of center)
            [ 0,  0,  0,  0], # Row 6
            [-1,  0,  0,  0], # Row 7
            [-1,  0,  0, -1], # Row 8
            [-1, -1, -1, -1]  # Row 9: South Kill Zone
        ]
        if pieces is None:
            self.pieces = [[None for _ in range(4)] for _ in range(10)]
        else:
            self.pieces = pieces
        self.anchor_pos = (None, None)  # Stores (y, x) of the anchored piece

    def is_on_board(self, y, x):
        """Checks if a coordinate is within the 10x4 array and not a side rail."""
        if 0 <= y < 10 and 0 <= x < 4:
            # Side rails are implied: any coordinate in the array is 'on' the board,
            # but -1 cells are the end-zones[cite: 49].
            return True
        return False

    def get_piece(self, y, x):
        """Returns the Piece object at (y, x) if it exists[cite: 10, 11]."""
        if self.is_on_board(y, x):
            return self.pieces[y][x]
        return "OUT_OF_BOUNDS" # Represents the side rails [cite: 49]

    def is_occupied(self, y, x):
        """True if there is a game piece on this tile."""
        piece = self.get_piece(y, x)
        return piece is not None and piece != "OUT_OF_BOUNDS"

    def is_kill_zone(self, y, x):
        """Checks if the piece has been pushed off into the -1 area[cite: 8, 20, 42]."""
        if self.is_on_board(y, x):
            return self.grid[y][x] == -1
        return False

    def get_valid_moves(self, start_y, start_x):
        """
        Returns a set of all (y, x) coordinates a piece at start_pos can reach.
        Uses BFS to find all connected empty spaces.
        """
        valid_destinations = set()
        visited = set()
        queue = deque([(start_y, start_x)])
        visited.add((start_y, start_x))
        
        # Directions: Up, Down, Left, Right (No diagonals [cite: 21])
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        
        while queue:
            curr_y, curr_x = queue.popleft()
            
            for dy, dx in directions:
                next_y, next_x = curr_y + dy, curr_x + dx
                
                # 1. Must be within 10x4 array bounds
                # 2. Must be a playable space (grid value 0, not -1)
                # 3. Must not be occupied by another piece [cite: 50]
                # 4. Must not have been visited already
                if ((next_y, next_x) not in visited and
                    self.is_on_board(next_y, next_x) and 
                    self.grid[next_y][next_x] == 0 and 
                    not self.is_occupied(next_y, next_x)):
                    
                    valid_destinations.add((next_y, next_x))
                    visited.add((next_y, next_x))
                    queue.append((next_y, next_x))
                    
        return valid_destinations

    def get_push_chain(self, start_y, start_x, dy, dx):
        """
        Returns a list of (y, x) coords for pieces in a push line.
        The chain includes the pushing square piece and all pieces in the push direction.
        """
        chain = []
        # Start from the square piece that's pushing
        chain.append((start_y, start_x))
        
        # Now check in the push direction for connected pieces
        curr_y, curr_x = start_y + dy, start_x + dx
        
        # Keep adding pieces to the chain until we hit an empty space or edge
        while self.is_on_board(curr_y, curr_x) and self.pieces[curr_y][curr_x] is not None:
            chain.append((curr_y, curr_x))
            curr_y += dy
            curr_x += dx
            
        return chain, (curr_y, curr_x)  # Returns the chain and the 'landing' spot

    def to_dict(self):
        """Convert PushFightBoard to dictionary for JSON serialization."""
        # Serialize pieces array - convert Piece objects to dicts or None
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
            'anchor_pos': self.anchor_pos
        }

    @staticmethod
    def from_dict(data):
        """Create PushFightBoard from dictionary."""
        from .pieces import Piece
        
        board = PushFightBoard()
        board.grid = data['grid']
        
        # Deserialize pieces array - convert dicts back to Piece objects
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
        board.anchor_pos = tuple(data['anchor_pos']) if data['anchor_pos'][0] is not None else (None, None)
        
        return board
