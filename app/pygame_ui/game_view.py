"""Game view and state management for PyGame interface."""

from app.engine.game_state import GameState
from app.storage import save_game, load_game, list_saves


class GameView:
    """Manages game state and view logic."""
    
    def __init__(self):
        """Initialize game view."""
        self.game = GameState.create_initial_game()
        self.message = ""
        self.message_timer = 0
    
    def new_game(self, custom_placement=False):
        """Start a new game."""
        if custom_placement:
            self.game = GameState.create_custom_game()
        else:
            self.game = GameState.create_initial_game()
        self.set_message("New game started!")
    
    def move_piece(self, from_pos, to_pos):
        """Move a piece."""
        from_y, from_x = from_pos
        to_y, to_x = to_pos
        
        if self.game.setup_mode or self.game.game_over:
            self.set_message("Cannot move in current state")
            return False
        
        if not self.game.can_move():
            self.set_message("Cannot move - must push now")
            return False
        
        piece = self.game.board.get_piece(from_y, from_x)
        if not piece or piece.team != self.game.current_player:
            self.set_message("Invalid piece selection")
            return False
        
        valid_moves = self.game.board.get_valid_moves(from_y, from_x)
        if (to_y, to_x) not in valid_moves:
            self.set_message("Invalid move destination")
            return False
        
        # Perform move
        self.game.board.pieces[from_y][from_x] = None
        self.game.board.pieces[to_y][to_x] = piece
        self.game.moves_made += 1
        self.set_message("Piece moved")
        return True
    
    def push_piece(self, piece_pos, direction):
        """Push with a piece."""
        y, x = piece_pos
        dy, dx = direction
        
        if self.game.setup_mode or self.game.game_over:
            self.set_message("Cannot push in current state")
            return False
        
        if not self.game.can_push():
            self.set_message("Not in push phase")
            return False
        
        success = self.game.perform_push(y, x, direction)
        if success:
            self.set_message("Push successful!")
            
            # Check for victory
            if self.game.game_over:
                self.set_message(f"Game Over! {self.game.winner.upper()} wins!")
            else:
                # Switch turns
                self.game.switch_turn()
        else:
            self.set_message("Invalid push")
        
        return success
    
    def place_piece(self, y, x, team, shape):
        """Place a piece during setup."""
        if not self.game.setup_mode:
            self.set_message("Not in setup mode")
            return False
        
        success, message = self.game.place_piece(y, x, team, shape)
        self.set_message(message)
        return success
    
    def remove_piece(self, y, x):
        """Remove a piece during setup."""
        if not self.game.setup_mode:
            self.set_message("Not in setup mode")
            return False
        
        success, message = self.game.remove_piece(y, x)
        self.set_message(message)
        return success
    
    def start_game(self):
        """Start the game after setup."""
        if not self.game.setup_mode:
            self.set_message("Game already started")
            return False
        
        success, message = self.game.start_game()
        self.set_message(message)
        return success
    
    def save_game(self, filename):
        """Save the current game."""
        try:
            save_path = save_game(self.game, filename)
            self.set_message(f"Game saved: {filename}")
            return True
        except Exception as e:
            self.set_message(f"Error saving: {e}")
            return False
    
    def load_game(self, filename):
        """Load a saved game."""
        try:
            self.game = load_game(filename)
            self.set_message(f"Game loaded: {filename}")
            return True
        except FileNotFoundError:
            self.set_message(f"Save file not found: {filename}")
            return False
        except Exception as e:
            self.set_message(f"Error loading: {e}")
            return False
    
    def set_message(self, message):
        """Set a status message."""
        self.message = message
        self.message_timer = 180  # ~3 seconds at 60 FPS
    
    def update(self):
        """Update view state (called each frame)."""
        if self.message_timer > 0:
            self.message_timer -= 1
        
        # Check for game over conditions
        if not self.game.game_over and not self.game.setup_mode:
            # Check if any player has 0 Square pieces
            self.game.check_game_over()
            
            # Check for trapped player (no legal pushes)
            if not self.game.game_over and not self.game.has_legal_push():
                self.game.game_over = True
                self.game.winner = 'brown' if self.game.current_player == 'white' else 'white'
                self.set_message(f"{self.game.winner.upper()} wins! (opponent trapped)")
    
    def get_message(self):
        """Get current status message."""
        if self.message_timer > 0:
            return self.message
        return ""
