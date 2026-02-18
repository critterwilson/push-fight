"""Input handling for PyGame interface."""

import pygame
from app.engine.game_state import GameState


class InputHandler:
    """Handles mouse and keyboard input."""
    
    def __init__(self, board_renderer):
        """
        Initialize input handler.
        
        Args:
            board_renderer: BoardRenderer instance for coordinate conversion
        """
        self.board_renderer = board_renderer
        self.selected_pos = None
        self.valid_moves = set()
        self.mode = 'move'  # 'move', 'push', 'setup'
    
    def handle_click(self, pos, game_state):
        """
        Handle mouse click.
        
        Args:
            pos: (x, y) screen coordinates
            game_state: Current GameState
            
        Returns:
            dict: Action dictionary or None
        """
        board_pos = self.board_renderer.screen_to_board(*pos)
        if board_pos is None:
            return None
        
        row, col = board_pos
        
        if game_state.setup_mode:
            return self._handle_setup_click(row, col, game_state)
        elif game_state.game_over:
            return None
        elif game_state.can_move():
            return self._handle_move_click(row, col, game_state)
        else:
            return self._handle_push_click(row, col, game_state)
    
    def _handle_setup_click(self, row, col, game_state):
        """Handle click during setup phase."""
        # For now, just return position - setup logic handled elsewhere
        return {'type': 'setup_click', 'pos': (row, col)}
    
    def _handle_move_click(self, row, col, game_state):
        """Handle click during move phase."""
        piece = game_state.board.get_piece(row, col)
        
        # If clicking on own piece, select it
        if piece and piece.team == game_state.current_player:
            self.selected_pos = (row, col)
            self.valid_moves = game_state.board.get_valid_moves(row, col)
            return None
        
        # If piece is selected and clicking valid destination, move
        if self.selected_pos and (row, col) in self.valid_moves:
            action = {
                'type': 'move',
                'from': self.selected_pos,
                'to': (row, col)
            }
            self.selected_pos = None
            self.valid_moves = set()
            return action
        
        # Clear selection if clicking elsewhere
        self.selected_pos = None
        self.valid_moves = set()
        return None
    
    def _handle_push_click(self, row, col, game_state):
        """Handle click during push phase."""
        piece = game_state.board.get_piece(row, col)
        
        # Select square piece for pushing (allow changing selection)
        if piece and piece.team == game_state.current_player and piece.shape == 'square':
            # If clicking the same piece, deselect it
            if self.selected_pos == (row, col):
                self.selected_pos = None
            else:
                # Select new piece (or change selection)
                self.selected_pos = (row, col)
            return None
        
        # If clicking empty space or invalid piece, clear selection
        if not piece or piece.team != game_state.current_player or piece.shape != 'square':
            self.selected_pos = None
        
        return None
    
    def handle_key(self, key, game_state):
        """
        Handle keyboard input.
        
        Args:
            key: PyGame key constant
            game_state: Current GameState
            
        Returns:
            dict: Action dictionary or None
        """
        # Direction keys for push
        if not game_state.can_move() and self.selected_pos:
            direction_map = {
                pygame.K_w: (-1, 0),  # Up
                pygame.K_s: (1, 0),   # Down
                pygame.K_a: (0, -1),   # Left
                pygame.K_d: (0, 1),    # Right
                pygame.K_UP: (-1, 0),
                pygame.K_DOWN: (1, 0),
                pygame.K_LEFT: (0, -1),
                pygame.K_RIGHT: (0, 1),
            }
            
            if key in direction_map:
                return {
                    'type': 'push',
                    'piece': self.selected_pos,
                    'direction': direction_map[key]
                }
        
        # Clear selection with Escape
        if key == pygame.K_ESCAPE:
            self.selected_pos = None
            self.valid_moves = set()
        
        return None
    
    def get_selected_pos(self):
        """Get currently selected position."""
        return self.selected_pos
    
    def get_valid_moves(self):
        """Get valid moves for selected piece."""
        return self.valid_moves
    
    def clear_selection(self):
        """Clear current selection."""
        self.selected_pos = None
        self.valid_moves = set()
