from .board import PushFightBoard
from .pieces import Piece

class GameState:
    def __init__(self, board=None, setup_mode=False):
        self.board = board if board else PushFightBoard()
        self.current_player = 'white'  # White team goes first [cite: 24]
        
        # Setup phase tracking
        self.setup_mode = setup_mode   # True during piece placement phase
        
        # Turn state tracking
        self.moves_made = 0            # Can be 0, 1, or 2 [cite: 24, 29]
        self.push_completed = False    # Turn ends after a mandatory push [cite: 25, 51]
        
        # Win state
        self.game_over = False
        self.winner = None

    def can_move(self):
        """Checks if the player still has moves left this turn."""
        return self.moves_made < 2 and not self.push_completed

    def can_push(self):
        """Checks if the player is in the push phase."""
        # A player can push even if they made 0 or 1 move [cite: 29]
        return not self.push_completed

    def switch_turn(self):
        """Resets counters and swaps players after a successful push."""
        if not self.push_completed:
            raise ValueError("You must push to complete your turn!")  # [cite: 31, 51]
            
        self.current_player = 'brown' if self.current_player == 'white' else 'white'
        self.moves_made = 0
        self.push_completed = False

    def check_for_victory(self, pushed_to_y, pushed_to_x):
        """Checks if the last push moved a piece into the kill zone (-1)."""
        if self.board.is_kill_zone(pushed_to_y, pushed_to_x):
            self.game_over = True
            self.winner = self.current_player
            return True
        return False

    def perform_push(self, y, x, direction):
        """
        direction: (dy, dx) e.g., (1, 0) for down
        """
        piece = self.board.get_piece(y, x)
        
        # 1. Validation: Must be a square piece to push [cite: 12, 30, 34]
        if not piece or piece.shape != 'square':
            return False
        
        # 1b. Validation: Must be the current player's piece
        if piece.team != self.current_player:
            return False
            
        dy, dx = direction
        chain, landing_spot = self.board.get_push_chain(y, x, dy, dx)
        
        # 2. Validation: The anchor cannot be moved [cite: 37, 39]
        if self.board.anchor_pos[0] is not None:  # Check if anchor exists
            for pos in chain:
                if pos == self.board.anchor_pos:
                    print("Push blocked by Anchor!")
                    return False

        # 3. Validation: Side Rail Check
        # If landing_spot is OUT_OF_BOUNDS (off the 10x4 array), it's a side rail 
        if not self.board.is_on_board(*landing_spot):
            print("Push blocked by side rail!")
            return False

        # 4. Execution: Shift pieces in reverse order to avoid overwriting
        for pos in reversed(chain):
            curr_y, curr_x = pos
            new_y, new_x = curr_y + dy, curr_x + dx
            
            moving_piece = self.board.pieces[curr_y][curr_x]
            self.board.pieces[curr_y][curr_x] = None # Clear old spot
            
            # 5. Victory Check: Did a piece land on a -1? [cite: 8, 20, 43]
            if self.board.is_kill_zone(new_y, new_x):
                self.handle_win(self.current_player)
            else:
                self.board.pieces[new_y][new_x] = moving_piece

        # 6. Update Anchor: Share one anchor on the square piece that pushed [cite: 36, 41]
        # The square piece moves to (y + dy, x + dx), so anchor goes there
        self.board.anchor_pos = (y + dy, x + dx)
        self.push_completed = True
        return True

    def handle_win(self, winner):
        """Sets the game over state and winner."""
        self.game_over = True
        self.winner = winner

    def has_legal_push(self):
        """Checks if the current player has any legal push available [cite: 51]."""
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
                        
                        # Check if anchor blocks this push
                        anchor_blocks = False
                        if self.board.anchor_pos[0] is not None:  # Check if anchor exists
                            for pos in chain:
                                if pos == self.board.anchor_pos:
                                    anchor_blocks = True
                                    break
                        
                        # Check if side rail blocks
                        side_rail_blocks = not self.board.is_on_board(*landing_spot)
                        
                        if not anchor_blocks and not side_rail_blocks:
                            return True
        
        return False

    @staticmethod
    def create_initial_game():
        board = PushFightBoard()
        
        # White Team (Rows 1-4) [cite: 14]
        # Most players put 4 pieces at the center line [cite: 16]
        board.pieces[4][0] = Piece('white', 'square')
        board.pieces[4][1] = Piece('white', 'square')
        board.pieces[4][2] = Piece('white', 'square')
        board.pieces[4][3] = Piece('white', 'round')
        board.pieces[3][1] = Piece('white', 'round')

        # Brown Team (Rows 5-8) [cite: 17]
        board.pieces[5][0] = Piece('brown', 'square')
        board.pieces[5][1] = Piece('brown', 'square')
        board.pieces[5][2] = Piece('brown', 'square')
        board.pieces[5][3] = Piece('brown', 'round')
        board.pieces[6][1] = Piece('brown', 'round')
        
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
            'winner': self.winner
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
        Brown team: rows 5-9 (south of center)
        """
        if team == 'white':
            return 0 <= y <= 4
        elif team == 'brown':
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
        squares = 0
        rounds = 0
        
        for y in range(10):
            for x in range(4):
                piece = self.board.get_piece(y, x)
                if piece and piece.team == team:
                    if piece.shape == 'square':
                        squares += 1
                    elif piece.shape == 'round':
                        rounds += 1
        
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
            team: 'white' or 'brown'
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
        if team not in ['white', 'brown']:
            return False, f"Invalid team: {team}. Must be 'white' or 'brown'"
        
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

    def can_start_game(self):
        """
        Check if both teams have valid piece placement (3 squares + 2 rounds each).
        
        Returns:
            tuple: (can_start: bool, message: str)
        """
        if not self.setup_mode:
            return False, "Game is not in setup mode"
        
        white_status = self.get_placement_status('white')
        brown_status = self.get_placement_status('brown')
        
        # Check white team
        if white_status['squares'] != 3:
            return False, f"White team must have exactly 3 square pieces (currently {white_status['squares']})"
        if white_status['rounds'] != 2:
            return False, f"White team must have exactly 2 round pieces (currently {white_status['rounds']})"
        
        # Check brown team
        if brown_status['squares'] != 3:
            return False, f"Brown team must have exactly 3 square pieces (currently {brown_status['squares']})"
        if brown_status['rounds'] != 2:
            return False, f"Brown team must have exactly 2 round pieces (currently {brown_status['rounds']})"
        
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
