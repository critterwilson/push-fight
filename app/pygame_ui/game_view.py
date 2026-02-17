"""Game view and state management for PyGame interface."""

import os
from app.engine.game_state import GameState
from app.storage import save_game, load_game, list_saves
from app.rl.agent import PushFightAgent


class GameView:
    """Manages game state and view logic."""
    
    def __init__(self):
        """Initialize game view."""
        self.game = GameState.create_initial_game()
        self.message = ""
        self.message_timer = 0
        self.game_mode = 'pvp'  # 'pvp' or 'pvcpu'
        self.ai_agent = None
        self.ai_team = 'black'  # AI plays as black (second player) by default
    
    def new_game(self, custom_placement=False):
        """Start a new game."""
        if custom_placement:
            self.game = GameState.create_custom_game()
        else:
            self.game = GameState.create_initial_game()
        self.set_message("New game started!")
    
    def set_game_mode(self, mode, ai_model_path=None):
        """
        Set game mode and load AI if needed.
        
        Args:
            mode: 'pvp' or 'pvcpu'
            ai_model_path: Path to AI model (required for pvcpu mode)
        """
        self.game_mode = mode
        
        if mode == 'pvcpu':
            if ai_model_path:
                try:
                    # Use the shared agent class
                    self.ai_agent = PushFightAgent(ai_model_path)
                    self.set_message(f"AI loaded from {ai_model_path}")
                except Exception as e:
                    self.set_message(f"Error loading AI: {e}")
                    self.game_mode = 'pvp'  # Fallback to PvP
            else:
                self.set_message("AI model path required for PvCPU mode")
                self.game_mode = 'pvp'
        else:
            self.ai_agent = None
            self.set_message("PvP mode enabled")
    
    def is_ai_turn(self):
        """Check if it's the AI's turn."""
        return (self.game_mode == 'pvcpu' and 
                self.ai_agent is not None and 
                self.game.current_player == self.ai_team and
                not self.game.game_over)
    
    def get_ai_action(self):
        """Get action from AI."""
        if not self.is_ai_turn():
            return None
        return self.ai_agent.get_action(self.game)
    
    def execute_ai_turn(self):
        """Execute one step of AI's turn (one move or one push)."""
        if not self.is_ai_turn():
            return False
        
        action = self.get_ai_action()
        if not action:
            return False

        if action['type'] == 'move':
            from_pos = action['from']
            to_pos = action['to']
            success, _ = self.game.perform_move(from_pos, to_pos)
            if success:
                self.set_message(f"AI moved ({from_pos[0]},{from_pos[1]}) -> ({to_pos[0]},{to_pos[1]})")
                return True

        elif action['type'] == 'push':
            y, x = action['piece']
            direction = action['direction']
            dir_names = {(-1, 0): 'up', (1, 0): 'down', (0, -1): 'left', (0, 1): 'right'}
            dir_name = dir_names.get(direction, 'unknown')
            
            if self.push_piece((y, x), direction):
                self.set_message(f"AI pushed ({y},{x}) {dir_name}")
                return True
        
        return False
    
    def move_piece(self, from_pos, to_pos):
        """Move a piece."""
        success, message = self.game.perform_move(from_pos, to_pos)
        self.set_message(message)
        return success
    
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
                self.game.winner = 'black' if self.game.current_player == 'white' else 'white'
                self.set_message(f"{self.game.winner.upper()} wins! (opponent trapped)")
    
    def get_message(self):
        """Get current status message."""
        if self.message_timer > 0:
            return self.message
        return ""
