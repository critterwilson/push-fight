"""UI components for PyGame interface."""

import pygame


class Button:
    """Simple button class for UI."""
    
    def __init__(self, x, y, width, height, text, color=(100, 100, 100), 
                 text_color=(255, 255, 255), font_size=20):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.text_color = text_color
        self.font = pygame.font.Font(None, font_size)
        self.hover_color = tuple(min(255, c + 30) for c in color)
        self.is_hovered = False
        self.is_clicked = False
    
    def draw(self, surface):
        """Draw the button on the surface."""
        color = self.hover_color if self.is_hovered else self.color
        
        # Shadow
        shadow_rect = self.rect.move(2, 2)
        pygame.draw.rect(surface, (10, 12, 15), shadow_rect, border_radius=6)
        
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        
        # Subtle highlight border
        highlight = tuple(min(255, c + 30) for c in color)
        pygame.draw.rect(surface, highlight, self.rect, 1, border_radius=6)
        
        # Draw text centered
        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)
    
    def handle_event(self, event):
        """Handle pygame events for button interaction."""
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.rect.collidepoint(event.pos):
                self.is_clicked = True
                return True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                was_clicked = self.is_clicked
                self.is_clicked = False
                if was_clicked and self.rect.collidepoint(event.pos):
                    return True
        return False
    
    def is_pressed(self):
        """Check if button was pressed (resets after check)."""
        if self.is_clicked:
            self.is_clicked = False
            return True
        return False


class StatusPanel:
    """Panel showing game status information."""
    
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
    
    def draw(self, surface, game_state, game_view=None):
        """Draw status information."""
        # Background
        pygame.draw.rect(surface, (33, 37, 43), self.rect)
        pygame.draw.rect(surface, (80, 80, 90), self.rect, 1)
        
        y_offset = 15
        x_offset = 15
        
        # Current player
        if game_state.game_over:
            winner_text = f"Winner: {game_state.winner.upper()}" if game_state.winner else "Draw"
            text_surface = self.font.render(winner_text, True, (255, 215, 0))
        else:
            # Check if it's AI's turn
            is_ai_turn = game_view and game_view.is_ai_turn() if game_view else False
            if is_ai_turn:
                text_surface = self.font.render("AI'S TURN", True, (255, 100, 100))
            else:
                player_color = (255, 255, 255) if game_state.current_player == 'white' else (150, 150, 150)
                text_surface = self.font.render(
                    f"{game_state.current_player.upper()}'S TURN", 
                    True, player_color
                )
        surface.blit(text_surface, (self.rect.x + x_offset, self.rect.y + y_offset))
        y_offset += 30
        
        # Moves made
        if not game_state.game_over:
            moves_text = f"Moves: {game_state.moves_made}/2"
            text_surface = self.small_font.render(moves_text, True, (200, 200, 200))
            surface.blit(text_surface, (self.rect.x + x_offset, self.rect.y + y_offset))
            y_offset += 25
            
            # Phase indicator
            if game_state.can_move():
                phase_text = "Phase: Move"
            else:
                phase_text = "Phase: Push (mandatory)"
            text_surface = self.small_font.render(phase_text, True, (200, 200, 200))
            surface.blit(text_surface, (self.rect.x + x_offset, self.rect.y + y_offset))
