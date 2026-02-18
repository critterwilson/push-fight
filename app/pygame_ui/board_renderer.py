"""Board rendering for PyGame interface."""

import pygame
from app.engine.game_state import GameState


class BoardRenderer:
    """Handles rendering of the game board."""
    
    def __init__(self, board_x, board_y, cell_size=50):
        """
        Initialize board renderer.
        
        Args:
            board_x: X position of board top-left corner
            board_y: Y position of board top-left corner
            cell_size: Size of each cell in pixels
        """
        self.board_x = board_x
        self.board_y = board_y
        self.cell_size = cell_size
        self.font = pygame.font.Font(None, 20)
        
        # Colors
        self.colors = {
            'board_bg': (33, 37, 43),
            'cell_light': (60, 64, 72),
            'cell_dark': (45, 49, 56),
            'kill_zone': (120, 50, 50),
            'highlight': (80, 100, 140),
            'valid_move': (60, 120, 80)
        }
    
    def board_to_screen(self, row, col):
        """Convert board coordinates to screen coordinates."""
        x = self.board_x + col * self.cell_size
        y = self.board_y + row * self.cell_size
        return x, y
    
    def screen_to_board(self, screen_x, screen_y):
        """Convert screen coordinates to board coordinates."""
        col = (screen_x - self.board_x) // self.cell_size
        row = (screen_y - self.board_y) // self.cell_size
        if 0 <= row < 10 and 0 <= col < 4:
            return row, col
        return None
    
    def draw_board(self, surface, game_state, selected_pos=None, valid_moves=None, 
                   highlight_positions=None):
        """
        Draw the game board.
        
        Args:
            surface: PyGame surface to draw on
            game_state: Current GameState
            selected_pos: (row, col) of selected piece
            valid_moves: Set of (row, col) tuples for valid move destinations
            highlight_positions: Set of (row, col) tuples to highlight
        """
        valid_moves = valid_moves or set()
        highlight_positions = highlight_positions or set()
        
        # Draw board background border
        border_rect = pygame.Rect(self.board_x - 5, self.board_y - 5, 
                                  (4 * self.cell_size) + 10, (10 * self.cell_size) + 10)
        pygame.draw.rect(surface, self.colors['board_bg'], border_rect)
        pygame.draw.rect(surface, (80, 80, 90), border_rect, 2)
        
        # Draw cells
        for row in range(10):
            for col in range(4):
                x, y = self.board_to_screen(row, col)
                rect = pygame.Rect(x, y, self.cell_size, self.cell_size)
                
                # Determine cell color
                if game_state.board.grid[row][col] == -1:
                    # Kill zone
                    cell_color = self.colors['kill_zone']
                else:
                    # Playable space
                    cell_color = self.colors['cell_light'] if (row + col) % 2 == 0 else self.colors['cell_dark']
                
                # Highlight valid moves
                if (row, col) in valid_moves:
                    cell_color = tuple(min(255, c + 50) for c in cell_color)
                    cell_color = (cell_color[0], min(255, cell_color[1] + 100), cell_color[2])
                
                # Highlight selected/highlighted positions
                if (row, col) == selected_pos or (row, col) in highlight_positions:
                    cell_color = tuple(min(255, c + 80) for c in cell_color)
                
                pygame.draw.rect(surface, cell_color, rect)
                pygame.draw.rect(surface, (35, 39, 46), rect, 1)
        
        # Draw pieces
        for row in range(10):
            for col in range(4):
                piece = game_state.board.get_piece(row, col)
                if piece and piece != "OUT_OF_BOUNDS":
                    x, y = self.board_to_screen(row, col)
                    center_x = x + self.cell_size // 2
                    center_y = y + self.cell_size // 2
                    
                    # Determine piece color
                    if piece.team == 'white':
                        piece_color = (220, 220, 225)
                        outline_color = (180, 180, 190)
                    else:
                        piece_color = (40, 44, 52)
                        outline_color = (20, 20, 25)
                    
                    # Check if anchored
                    is_anchor = (row, col) == game_state.board.anchor_pos
                    if is_anchor:
                        outline_color = (255, 0, 0)  # Red for anchor
                    
                    # Draw piece shape
                    radius = int(self.cell_size * 0.35)
                    if piece.shape == 'square':
                        # Draw square
                        square_rect = pygame.Rect(
                            center_x - radius, center_y - radius,
                            radius * 2, radius * 2
                        )
                        pygame.draw.rect(surface, piece_color, square_rect)
                        pygame.draw.rect(surface, outline_color, square_rect, 2)
                        # Inner detail
                        inner_rect = square_rect.inflate(-10, -10)
                        pygame.draw.rect(surface, outline_color, inner_rect, 1)
                    else:
                        # Draw circle
                        pygame.draw.circle(surface, piece_color, (center_x, center_y), radius)
                        pygame.draw.circle(surface, outline_color, (center_x, center_y), radius, 2)
                        # Inner detail
                        pygame.draw.circle(surface, outline_color, (center_x, center_y), radius - 5, 1)
                    
                    # Draw anchor indicator
                    if is_anchor:
                        anchor_size = 8
                        anchor_rect = pygame.Rect(
                            center_x - anchor_size // 2, center_y - anchor_size // 2,
                            anchor_size, anchor_size
                        )
                        pygame.draw.rect(surface, (255, 0, 0), anchor_rect)
        
        # Draw coordinates (optional, for debugging)
        # for row in range(10):
        #     for col in range(4):
        #         x, y = self.board_to_screen(row, col)
        #         coord_text = f"{row},{col}"
        #         text_surface = self.font.render(coord_text, True, (100, 100, 100))
        #         surface.blit(text_surface, (x + 2, y + 2))
