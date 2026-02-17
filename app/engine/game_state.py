from datetime import datetime
from .board import PushFightBoard
from .pieces import Piece

class GameState:
    def __init__(self, board=None, setup_mode=False):
        self.board = board if board else PushFightBoard()
        self.current_player = 'white'  # White team goes first 
        
        # Setup phase tracking
        self.setup_mode = setup_mode   # True during piece placement phase
        
        # Turn state tracking
        self.moves_made = 0            # Can be 0, 1, or 2 
        self.push_completed = False    # Turn ends after a mandatory push 
        
        # Win state
        self.game_over = False
        self.winner = None
        
        # Track pieces pushed off the board (for win condition)
        # Win condition: 2 squares OR 1 round piece pushed off
        self.pieces_pushed_off = {
            'white': {'squares': 0, 'rounds': 0},
            'black': {'squares': 0, 'rounds': 0}
        }
        self.move_log = []

    def can_move(self):
        """Checks if the player still has moves left this turn."""
        return self.moves_made < 2 and not self.push_completed

    def can_push(self):
        """Checks if the player is in the push phase."""
        # A player can push even if they made 0 or 1 move 
        return not self.push_completed

    def switch_turn(self):
        """Resets counters and swaps players after a successful push."""
        if not self.push_completed:
            raise ValueError("You must push to complete your turn!")  # 
            
        self.current_player = 'black' if self.current_player == 'white' else 'white'
        self.moves_made = 0
        self.push_completed = False

    def count_pieces(self, team, shape=None):
        """
        Count pieces on the board for a team, optionally filtered by shape.
        
        Args:
            team: 'white' or 'black'
            shape: 'square', 'round', or None (count all pieces)
            
        Returns:
            int: Number of pieces matching criteria
        """
        count = 0
        for y in range(10):
            for x in range(4):
                piece = self.board.get_piece(y, x)
                if (piece and piece != "OUT_OF_BOUNDS" and piece.team == team):
                    if shape is None or piece.shape == shape:
                        count += 1
        return count
    
    def count_square_pieces(self, team):
        """
        Count the number of square pieces remaining on the board for a team.
        
        Args:
            team: 'white' or 'black'
            
        Returns:
            int: Number of square pieces on the board
        """
        return self.count_pieces(team, 'square')
    
    def count_round_pieces(self, team):
        """
        Count the number of round pieces remaining on the board for a team.
        
        Args:
            team: 'white' or 'black'
            
        Returns:
            int: Number of round pieces on the board
        """
        return self.count_pieces(team, 'round')
    
    def perform_move(self, from_pos, to_pos):
        """
        Execute a move action with validation and logging.
        Returns: (success, message)
        """
        from_y, from_x = from_pos
        to_y, to_x = to_pos
        
        if self.setup_mode or self.game_over:
            return False, "Cannot move in current state"
            
        if not self.can_move():
            return False, "Cannot move - must push now"
            
        piece = self.board.get_piece(from_y, from_x)
        if not piece or piece.team != self.current_player:
            return False, "Invalid piece selection"
            
        valid_moves = self.board.get_valid_moves(from_y, from_x)
        if (to_y, to_x) not in valid_moves:
            return False, "Invalid move destination"
            
        # Execute
        self.board.pieces[from_y][from_x] = None
        self.board.pieces[to_y][to_x] = piece
        self.moves_made += 1
        
        # Log
        self.log_action('move', from_pos=from_pos, to_pos=to_pos)
        
        return True, "Piece moved"

    def log_action(self, action_type, **kwargs):
        """Log an action to the history."""
        entry = {
            'type': action_type,
            'player': self.current_player,
            'timestamp': datetime.now().isoformat(),
            **kwargs
        }
        self.move_log.append(entry)

    def perform_push(self, y, x, direction):
        """
        direction: (dy, dx) e.g., (1, 0) for down
        
        New rule: Pushes can be attempted against anchored pieces (they just won't move anything).
        Side rails still block pushes.
        """
        piece = self.board.get_piece(y, x)
        
        # 1. Validation: Must be a square piece to push 
        if not piece or piece.shape != 'square':
            return False
        
        # 1b. Validation: Must be the current player's piece
        if piece.team != self.current_player:
            return False
            
        dy, dx = direction
        chain, landing_spot = self.board.get_push_chain(y, x, dy, dx)
        
        # 2. Validation: Side Rail Check
        # If landing_spot is OUT_OF_BOUNDS (off the 10x4 array), it's a side rail 
        if not self.board.is_on_board(*landing_spot):
            # Silently fail during RL training (no print)
            return False

        # 3. Kill Zone Check - ALLOW pushes into kill zones (that's how you win!)
        # We'll handle pieces pushed into kill zones by removing them and checking for victory

        # 4. Check if anchor is in the chain (but allow the push anyway)
        anchor_in_chain = False
        if self.board.anchor_pos[0] is not None:
            for pos in chain:
                if pos == self.board.anchor_pos:
                    anchor_in_chain = True
                    break

        # 5. Execution: Shift pieces in reverse order to avoid overwriting
        # If anchor is in chain, pieces before anchor can move, but anchor and pieces after it cannot
        pieces_moved = False
        
        # Find anchor position in chain to determine what can move
        anchor_index = -1
        if anchor_in_chain:
            for i, pos in enumerate(chain):
                if pos == self.board.anchor_pos:
                    anchor_index = i
                    break
        
        # Track pieces pushed into kill zone (multiple pieces can be pushed at once)
        pieces_pushed_off = []  # List of (piece, team) tuples
        
        # Move pieces in reverse order (from end of chain to start)
        for i in range(len(chain) - 1, -1, -1):
            pos = chain[i]
            curr_y, curr_x = pos
            
            # If anchor is in chain, don't move anchor or any pieces after it (earlier in chain)
            if anchor_in_chain and i <= anchor_index:
                # This is the anchor or a piece after it - don't move
                continue
            
            new_y, new_x = curr_y + dy, curr_x + dx
            
            # Safety check: don't move if destination would be the anchor position
            if self.board.anchor_pos[0] is not None and (new_y, new_x) == self.board.anchor_pos:
                # Can't move into anchor position - this piece is blocked by anchor
                # Don't clear the piece's current position - it stays where it is
                continue
            
            moving_piece = self.board.pieces[curr_y][curr_x]
            if moving_piece is None:
                # Piece already moved or doesn't exist - skip
                continue
            
            # Check if destination is already occupied (shouldn't happen in normal flow, but safety check)
            if self.board.pieces[new_y][new_x] is not None:
                # Destination occupied - can't move here, don't clear current position
                continue
            
            # Check if destination is kill zone - ALLOW it! (this is how you win)
            if self.board.is_kill_zone(new_y, new_x):
                # Piece is pushed into kill zone - remove it from board
                self.board.pieces[curr_y][curr_x] = None  # Clear old spot
                pieces_pushed_off.append((moving_piece, moving_piece.team))
                pieces_moved = True
                # Don't place piece in kill zone - it's removed from play
            else:
                # Normal move - place piece at destination
                self.board.pieces[curr_y][curr_x] = None  # Clear old spot
                self.board.pieces[new_y][new_x] = moving_piece
                pieces_moved = True
        
        # Log the push action
        self.log_action('push', piece=(y, x), direction=direction)

        # 6. Update Anchor: Share one anchor on the square piece that pushed 
        # The square piece moves to (y + dy, x + dx), so anchor goes there
        # Note: Even if nothing moved (anchor blocked), we still update the anchor position
        # If the push was blocked by an anchor, the pusher didn't move, so anchor stays at (y, x)
        if anchor_in_chain:
            anchor_y, anchor_x = y, x
        else:
            anchor_y, anchor_x = y + dy, x + dx
            
        if self.board.is_on_board(anchor_y, anchor_x) and not self.board.is_kill_zone(anchor_y, anchor_x):
            self.board.anchor_pos = (anchor_y, anchor_x)
        else:
            # Anchor piece was pushed into kill zone, clear anchor
            self.board.anchor_pos = (None, None)
        
        # 7. Check for victory if pieces were pushed into kill zone
        if pieces_pushed_off:
            # Track all pieces that were pushed off
            for piece, team in pieces_pushed_off:
                if piece.shape == 'square':
                    self.pieces_pushed_off[team]['squares'] += 1
                else:  # round
                    self.pieces_pushed_off[team]['rounds'] += 1
            
            # Check win condition once after tracking all pieces
            # Use check_game_over() to avoid code duplication
            if self.check_game_over():
                self.push_completed = True
                return True
        
        # Push completed successfully (no win)
        self.push_completed = True
        return True
    
    def check_game_over(self):
        """
        Check if the game should be over based on current board state.
        Win condition: 2 squares OR 1 round piece pushed off the board.
        
        Returns:
            bool: True if game is over, False otherwise
        """
        if self.game_over:
            return True
        
        # Check win condition: 2 squares OR 1 round piece pushed off
        white_squares_off = self.pieces_pushed_off['white']['squares']
        white_rounds_off = self.pieces_pushed_off['white']['rounds']
        black_squares_off = self.pieces_pushed_off['black']['squares']
        black_rounds_off = self.pieces_pushed_off['black']['rounds']
        
        # White loses if 2 squares or 1 round pushed off
        if white_squares_off >= 2 or white_rounds_off >= 1:
            self.game_over = True
            self.winner = 'black'
            return True
        
        # black loses if 2 squares or 1 round pushed off
        if black_squares_off >= 2 or black_rounds_off >= 1:
            self.game_over = True
            self.winner = 'white'
            return True
        
        return False

    def has_legal_push(self):
        """Checks if the current player has any legal push available ."""
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # Up, Down, Left, Right
        
        for y in range(10):
            for x in range(4):
                piece = self.board.get_piece(y, x)
                if (piece and 
                    piece.team == self.current_player and 
                    piece.shape == 'square'):
                    
                    for dy, dx in directions:
                        # Try a test push to see if it's legal
                        chain, landing_spot = self.board.get_push_chain(y, x, dy, dx)
                        
                        # Check if side rail blocks (anchor no longer blocks)
                        side_rail_blocks = not self.board.is_on_board(*landing_spot)
                        
                        if not side_rail_blocks:
                            return True
        
        return False

    @staticmethod
    def create_initial_game():
        board = PushFightBoard()
        
        # White Team (Rows 1-4) 
        # Most players put 4 pieces at the center line 
        board.pieces[4][0] = Piece('white', 'square')
        board.pieces[4][1] = Piece('white', 'square')
        board.pieces[4][2] = Piece('white', 'square')
        board.pieces[4][3] = Piece('white', 'round')
        board.pieces[3][1] = Piece('white', 'round')

        # black Team (Rows 5-8) 
        board.pieces[5][0] = Piece('black', 'square')
        board.pieces[5][1] = Piece('black', 'square')
        board.pieces[5][2] = Piece('black', 'square')
        board.pieces[5][3] = Piece('black', 'round')
        board.pieces[6][1] = Piece('black', 'round')
        
        return GameState(board)

    def to_dict(self):
        """Convert GameState to dictionary for JSON serialization."""
        return {
            'board': self.board.to_dict(),
            'current_player': self.current_player,
            'setup_mode': self.setup_mode,
            'moves_made': self.moves_made,
            'push_completed': self.push_completed,
            'game_over': self.game_over,
            'winner': self.winner,
            'pieces_pushed_off': self.pieces_pushed_off
        }

    @staticmethod
    def from_dict(data):
        """Create GameState from dictionary."""
        board = PushFightBoard.from_dict(data['board'])
        setup_mode = data.get('setup_mode', False)  # Backward compatibility
        game = GameState(board, setup_mode=setup_mode)
        game.current_player = data['current_player']
        game.moves_made = data['moves_made']
        game.push_completed = data['push_completed']
        game.game_over = data['game_over']
        game.winner = data['winner']
        # Handle backward compatibility - initialize if not present
        game.pieces_pushed_off = data.get('pieces_pushed_off', {
            'white': {'squares': 0, 'rounds': 0},
            'black': {'squares': 0, 'rounds': 0}
        })
        return game

    def save_to_file(self, filepath):
        """Save game state to a JSON file."""
        import json
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load_from_file(filepath):
        """Load game state from a JSON file."""
        import json
        with open(filepath, 'r') as f:
            data = json.load(f)
        return GameState.from_dict(data)

    @staticmethod
    def create_custom_game():
        """Create an empty game state for custom piece placement."""
        board = PushFightBoard()
        return GameState(board, setup_mode=True)

    def _is_on_player_side(self, y, team):
        """
        Check if a position is on the player's side of the centerline.
        White team: rows 0-4 (north of center)
        black team: rows 5-9 (south of center)
        """
        if team == 'white':
            return 0 <= y <= 4
        elif team == 'black':
            return 5 <= y <= 9
        return False

    def _is_playable_space(self, y, x):
        """Check if a position is a playable space (not kill zone)."""
        if not self.board.is_on_board(y, x):
            return False
        return self.board.grid[y][x] == 0

    def get_placement_status(self, team):
        """
        Get the current placement status for a team.
        
        Returns:
            dict: {'squares': int, 'rounds': int, 'total': int}
        """
        squares = self.count_square_pieces(team)
        rounds = self.count_round_pieces(team)
        
        return {
            'squares': squares,
            'rounds': rounds,
            'total': squares + rounds
        }

    def place_piece(self, y, x, team, shape):
        """
        Place a piece during setup phase with validation.
        
        Args:
            y: Row (0-9)
            x: Column (0-3)
            team: 'white' or 'black'
            shape: 'square' or 'round'
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.setup_mode:
            return False, "Game is not in setup mode"
        
        # Validate shape
        if shape not in ['square', 'round']:
            return False, f"Invalid shape: {shape}. Must be 'square' or 'round'"
        
        # Validate team
        if team not in ['white', 'black']:
            return False, f"Invalid team: {team}. Must be 'white' or 'black'"
        
        # Check if position is on player's side
        if not self._is_on_player_side(y, team):
            return False, f"Position ({y}, {x}) is not on {team} team's side of the centerline"
        
        # Check if position is playable (not kill zone)
        if not self._is_playable_space(y, x):
            return False, f"Position ({y}, {x}) is not a playable space (kill zone or out of bounds)"
        
        # Check if position is already occupied
        if self.board.is_occupied(y, x):
            return False, f"Position ({y}, {x}) is already occupied"
        
        # Check placement limits
        status = self.get_placement_status(team)
        if shape == 'square':
            if status['squares'] >= 3:
                return False, f"{team} team already has 3 square pieces (maximum)"
        elif shape == 'round':
            if status['rounds'] >= 2:
                return False, f"{team} team already has 2 round pieces (maximum)"
        
        # Place the piece
        self.board.pieces[y][x] = Piece(team, shape)
        return True, f"{team} {shape} piece placed at ({y}, {x})"

    def remove_piece(self, y, x):
        """
        Remove a piece during setup phase.
        
        Args:
            y: Row (0-9)
            x: Column (0-3)
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.setup_mode:
            return False, "Game is not in setup mode"
        
        if not self.board.is_on_board(y, x):
            return False, f"Position ({y}, {x}) is out of bounds"
        
        piece = self.board.get_piece(y, x)
        if piece is None:
            return False, f"No piece at position ({y}, {x})"
        
        # Remove the piece
        self.board.pieces[y][x] = None
        return True, f"Piece removed from ({y}, {x})"

    def _validate_team_placement(self, team, required_squares=3, required_rounds=2):
        """
        Validate that a team has the required number of pieces.
        
        Args:
            team: 'white' or 'black'
            required_squares: Required number of square pieces
            required_rounds: Required number of round pieces
            
        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        status = self.get_placement_status(team)
        if status['squares'] != required_squares:
            return False, f"{team.capitalize()} team must have exactly {required_squares} square pieces (currently {status['squares']})"
        if status['rounds'] != required_rounds:
            return False, f"{team.capitalize()} team must have exactly {required_rounds} round pieces (currently {status['rounds']})"
        return True, None
    
    def can_start_game(self):
        """
        Check if both teams have valid piece placement (3 squares + 2 rounds each).
        
        Returns:
            tuple: (can_start: bool, message: str)
        """
        if not self.setup_mode:
            return False, "Game is not in setup mode"
        
        # Validate white team
        is_valid, error = self._validate_team_placement('white')
        if not is_valid:
            return False, error
        
        # Validate black team
        is_valid, error = self._validate_team_placement('black')
        if not is_valid:
            return False, error
        
        return True, "Both teams have valid piece placement"

    def start_game(self):
        """
        Transition from setup mode to active game.
        
        Returns:
            tuple: (success: bool, message: str)
        """
        can_start, message = self.can_start_game()
        if not can_start:
            return False, message
        
        self.setup_mode = False
        self.current_player = 'white'  # White goes first
        return True, "Game started! White team goes first."
