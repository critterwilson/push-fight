"""Main PyGame application entry point."""

import pygame
import sys
from app.pygame_ui.game_view import GameView
from app.pygame_ui.board_renderer import BoardRenderer
from app.pygame_ui.input_handler import InputHandler
from app.pygame_ui.ui_components import Button, StatusPanel


# Constants
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 700
BOARD_X = 50
BOARD_Y = 50
CELL_SIZE = 50
FPS = 60

# Colors
BACKGROUND = (20, 20, 20)
TEXT_COLOR = (255, 255, 255)


def main():
    """Main PyGame application loop."""
    pygame.init()
    
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Push Fight")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 36)
    small_font = pygame.font.Font(None, 24)
    
    # Initialize components
    game_view = GameView()
    board_renderer = BoardRenderer(BOARD_X, BOARD_Y, CELL_SIZE)
    input_handler = InputHandler(board_renderer)
    
    # UI components
    status_panel = StatusPanel(500, 50, 350, 150)
    
    # Buttons
    new_game_btn = Button(500, 220, 150, 40, "New Game", (50, 150, 50))
    save_btn = Button(500, 270, 150, 40, "Save Game", (50, 100, 150))
    load_btn = Button(500, 320, 150, 40, "Load Game", (150, 100, 50))
    skip_moves_btn = Button(500, 370, 150, 40, "Skip Moves", (150, 150, 50))
    
    # Direction buttons for push phase
    direction_btn_size = 50
    direction_btn_x = 500
    direction_btn_y = 420
    up_btn = Button(direction_btn_x + direction_btn_size, direction_btn_y, 
                    direction_btn_size, direction_btn_size, "↑", (80, 80, 80), font_size=30)
    down_btn = Button(direction_btn_x + direction_btn_size, direction_btn_y + direction_btn_size + 5, 
                      direction_btn_size, direction_btn_size, "↓", (80, 80, 80), font_size=30)
    left_btn = Button(direction_btn_x, direction_btn_y + direction_btn_size + 5, 
                      direction_btn_size, direction_btn_size, "←", (80, 80, 80), font_size=30)
    right_btn = Button(direction_btn_x + direction_btn_size * 2, direction_btn_y + direction_btn_size + 5, 
                       direction_btn_size, direction_btn_size, "→", (80, 80, 80), font_size=30)
    
    running = True
    show_dialog = False
    dialog_mode = None  # 'save' or 'load'
    dialog_filename = ""
    
    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    # Check main buttons
                    if new_game_btn.handle_event(event):
                        game_view.new_game()
                        input_handler.clear_selection()
                    elif save_btn.handle_event(event):
                        show_dialog = True
                        dialog_mode = 'save'
                        dialog_filename = ""
                    elif load_btn.handle_event(event):
                        show_dialog = True
                        dialog_mode = 'load'
                        dialog_filename = ""
                    # Check skip moves button
                    elif skip_moves_btn.handle_event(event):
                        if game_view.game.can_move():
                            game_view.set_message("Moves skipped - proceeding to push phase")
                            # Skip remaining moves by setting moves_made to 2
                            game_view.game.moves_made = 2
                    # Check direction buttons (only during push phase with selected piece)
                    elif input_handler.get_selected_pos() and not game_view.game.can_move():
                        selected_pos = input_handler.get_selected_pos()
                        piece = game_view.game.board.get_piece(*selected_pos)
                        if piece and piece.shape == 'square':
                            direction = None
                            if up_btn.handle_event(event):
                                direction = (-1, 0)
                            elif down_btn.handle_event(event):
                                direction = (1, 0)
                            elif left_btn.handle_event(event):
                                direction = (0, -1)
                            elif right_btn.handle_event(event):
                                direction = (0, 1)
                            
                            if direction:
                                # Only perform push when direction is selected
                                if game_view.push_piece(selected_pos, direction):
                                    input_handler.clear_selection()
                    else:
                        # Handle board click (for selecting/changing piece selection)
                        action = input_handler.handle_click(event.pos, game_view.game)
                        if action:
                            if action['type'] == 'move':
                                game_view.move_piece(action['from'], action['to'])
                                input_handler.clear_selection()
                            # Note: push action from keyboard is handled separately
                            # Board clicks during push phase just change selection
            
            elif event.type == pygame.KEYDOWN:
                # Handle keyboard input
                action = input_handler.handle_key(event.key, game_view.game)
                if action and action['type'] == 'push':
                    game_view.push_piece(action['piece'], action['direction'])
                    input_handler.clear_selection()
                
                # Handle save/load dialog
                if show_dialog:
                    if event.key == pygame.K_RETURN:
                        if dialog_filename:
                            if dialog_mode == 'save':
                                game_view.save_game(dialog_filename)
                            else:
                                game_view.load_game(dialog_filename)
                            show_dialog = False
                            dialog_mode = None
                            dialog_filename = ""
                    elif event.key == pygame.K_ESCAPE:
                        show_dialog = False
                        dialog_mode = None
                        dialog_filename = ""
                    elif event.key == pygame.K_BACKSPACE:
                        dialog_filename = dialog_filename[:-1]
                    else:
                        # Add character (simple, no special handling)
                        if event.unicode.isprintable():
                            dialog_filename += event.unicode
            
            # Update button hover states
            new_game_btn.handle_event(event)
            save_btn.handle_event(event)
            load_btn.handle_event(event)
            skip_moves_btn.handle_event(event)
            
            # Update direction buttons hover states
            if input_handler.get_selected_pos() and not game_view.game.can_move():
                selected_pos = input_handler.get_selected_pos()
                piece = game_view.game.board.get_piece(*selected_pos)
                if piece and piece.shape == 'square':
                    up_btn.handle_event(event)
                    down_btn.handle_event(event)
                    left_btn.handle_event(event)
                    right_btn.handle_event(event)
        
        # Update game state
        game_view.update()
        
        # Draw everything
        screen.fill(BACKGROUND)
        
        # Draw board
        selected_pos = input_handler.get_selected_pos()
        valid_moves = input_handler.get_valid_moves()
        board_renderer.draw_board(
            screen, game_view.game, 
            selected_pos=selected_pos,
            valid_moves=valid_moves
        )
        
        # Draw status panel
        status_panel.draw(screen, game_view.game)
        
        # Draw buttons
        new_game_btn.draw(screen)
        save_btn.draw(screen)
        load_btn.draw(screen)
        
        # Draw skip moves button (only during move phase)
        if game_view.game.can_move() and not game_view.game.game_over:
            skip_moves_btn.draw(screen)
        
        # Draw direction buttons (only during push phase with selected square piece)
        selected_pos = input_handler.get_selected_pos()
        if selected_pos and not game_view.game.can_move() and not game_view.game.game_over:
            piece = game_view.game.board.get_piece(*selected_pos)
            if piece and piece.shape == 'square' and piece.team == game_view.game.current_player:
                # Draw label
                label_text = small_font.render("Push Direction:", True, TEXT_COLOR)
                screen.blit(label_text, (direction_btn_x, direction_btn_y - 25))
                
                # Draw direction buttons
                up_btn.draw(screen)
                down_btn.draw(screen)
                left_btn.draw(screen)
                right_btn.draw(screen)
        
        # Draw message
        message = game_view.get_message()
        if message:
            text_surface = small_font.render(message, True, (255, 255, 0))
            screen.blit(text_surface, (50, WINDOW_HEIGHT - 40))
        
        # Draw save/load dialog
        if show_dialog:
            # Semi-transparent overlay
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
            overlay.set_alpha(200)
            overlay.fill((0, 0, 0))
            screen.blit(overlay, (0, 0))
            
            # Dialog box
            dialog_rect = pygame.Rect(250, 250, 400, 150)
            pygame.draw.rect(screen, (50, 50, 50), dialog_rect)
            pygame.draw.rect(screen, (255, 255, 255), dialog_rect, 2)
            
            # Text
            mode_text = "Save" if dialog_mode == 'save' else "Load"
            prompt_text = small_font.render(f"{mode_text} game - Enter filename:", True, TEXT_COLOR)
            screen.blit(prompt_text, (dialog_rect.x + 20, dialog_rect.y + 20))
            
            filename_text = small_font.render(dialog_filename + "_", True, TEXT_COLOR)
            screen.blit(filename_text, (dialog_rect.x + 20, dialog_rect.y + 60))
            
            hint_text = small_font.render("Press Enter to confirm, Esc to cancel", True, (150, 150, 150))
            screen.blit(hint_text, (dialog_rect.x + 20, dialog_rect.y + 100))
        
        pygame.display.flip()
        clock.tick(FPS)
    
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
