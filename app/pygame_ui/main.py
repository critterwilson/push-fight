"""Main PyGame application entry point."""

import pygame
import sys
import os
from app.pygame_ui.game_view import GameView
from app.pygame_ui.board_renderer import BoardRenderer
from app.pygame_ui.input_handler import InputHandler
from app.pygame_ui.ui_components import Button, StatusPanel


# Constants
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 700
BOARD_X = 100
BOARD_Y = 50
CELL_SIZE = 60
FPS = 60

# Colors
BACKGROUND = (20, 24, 30)
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
    new_game_btn = Button(500, 220, 150, 40, "New Game", (46, 139, 87))
    pvp_btn = Button(500, 270, 70, 30, "PvP", (70, 130, 180))
    pvcpu_btn = Button(580, 270, 70, 30, "PvCPU", (205, 92, 92))
    save_btn = Button(500, 310, 150, 40, "Save Game", (60, 70, 80))
    load_btn = Button(500, 360, 150, 40, "Load Game", (60, 70, 80))
    skip_moves_btn = Button(500, 410, 150, 40, "Skip Moves", (180, 140, 40))
    
    # Direction buttons for push phase
    direction_btn_size = 50
    direction_btn_x = 500
    direction_btn_y = 460
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
    dialog_mode = None  # 'save', 'load', or 'ai_model'
    dialog_filename = ""
    model_buttons = []
    
    ai_move_timer = 0
    AI_MOVE_DELAY = 600  # ms between AI actions
    
    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    # Handle dialog interactions first
                    if show_dialog and dialog_mode == 'ai_model_select':
                        for path, btn in model_buttons:
                            if btn.handle_event(event):
                                game_view.set_game_mode('pvcpu', path)
                                show_dialog = False
                                dialog_mode = None
                                break
                    
                    # Check main buttons
                    elif not show_dialog and new_game_btn.handle_event(event):
                        game_view.new_game()
                        input_handler.clear_selection()
                    elif not show_dialog and pvp_btn.handle_event(event):
                        game_view.set_game_mode('pvp')
                        input_handler.clear_selection()
                    elif not show_dialog and pvcpu_btn.handle_event(event):
                        # Check for models directory
                        models_dir = "models"
                        if not os.path.exists(models_dir):
                            try:
                                os.makedirs(models_dir)
                            except OSError:
                                pass
                        
                        # Find .zip files
                        models = []
                        if os.path.exists(models_dir):
                            models = [f for f in os.listdir(models_dir) if f.endswith(".zip")]
                        
                        if models:
                            show_dialog = True
                            dialog_mode = 'ai_model_select'
                            model_buttons = []
                            
                            dialog_width = 300
                            dialog_x = (WINDOW_WIDTH - dialog_width) // 2
                            start_y = 250
                            
                            for i, model in enumerate(models):
                                # Clean name
                                name = model.replace("push_fight_", "").replace(".zip", "")
                                if not name: name = model
                                
                                btn_width = 200
                                btn_x = dialog_x + (dialog_width - btn_width) // 2
                                btn_y = start_y + 40 + (i * 45)
                                
                                btn = Button(btn_x, btn_y, btn_width, 35, name, (70, 80, 90))
                                model_buttons.append((os.path.join(models_dir, model), btn))
                        else:
                            # Fallback to text input if no models found
                            show_dialog = True
                            dialog_mode = 'ai_model'
                            dialog_filename = "models/push_fight_ppo"
                    elif not show_dialog and save_btn.handle_event(event):
                        show_dialog = True
                        dialog_mode = 'save'
                        dialog_filename = ""
                    elif not show_dialog and load_btn.handle_event(event):
                        show_dialog = True
                        dialog_mode = 'load'
                        dialog_filename = ""
                    # Check skip moves button
                    elif not show_dialog and skip_moves_btn.handle_event(event):
                        if game_view.game.can_move():
                            game_view.set_message("Moves skipped - proceeding to push phase")
                            # Skip remaining moves by setting moves_made to 2
                            game_view.game.moves_made = 2
                    # Check direction buttons (only during push phase with selected piece)
                    elif not show_dialog and input_handler.get_selected_pos() and not game_view.game.can_move():
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
                        # Only handle board clicks if it's not AI's turn
                        if not show_dialog and not game_view.is_ai_turn():
                            # Handle board click (for selecting/changing piece selection)
                            action = input_handler.handle_click(event.pos, game_view.game)
                            if action:
                                if action['type'] == 'move':
                                    game_view.move_piece(action['from'], action['to'])
                                    input_handler.clear_selection()
                                # Note: push action from keyboard is handled separately
                                # Board clicks during push phase just change selection
            
            elif event.type == pygame.KEYDOWN:
                # Only handle keyboard input if it's not AI's turn
                if not show_dialog and not game_view.is_ai_turn():
                    # Handle keyboard input
                    action = input_handler.handle_key(event.key, game_view.game)
                    if action and action['type'] == 'push':
                        game_view.push_piece(action['piece'], action['direction'])
                        input_handler.clear_selection()
                
                # Handle save/load/ai_model dialog
                if show_dialog:
                    if dialog_mode == 'ai_model_select':
                        if event.key == pygame.K_ESCAPE:
                            show_dialog = False
                            dialog_mode = None
                    
                    elif event.key == pygame.K_RETURN:
                        if dialog_filename:
                            if dialog_mode == 'save':
                                game_view.save_game(dialog_filename)
                            elif dialog_mode == 'load':
                                game_view.load_game(dialog_filename)
                            elif dialog_mode == 'ai_model':
                                game_view.set_game_mode('pvcpu', dialog_filename)
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
            if show_dialog and dialog_mode == 'ai_model_select':
                for _, btn in model_buttons:
                    btn.handle_event(event)
            else:
                new_game_btn.handle_event(event)
                pvp_btn.handle_event(event)
                pvcpu_btn.handle_event(event)
                save_btn.handle_event(event)
                load_btn.handle_event(event)
                skip_moves_btn.handle_event(event)
            
            # Update direction buttons hover states
            if not show_dialog and input_handler.get_selected_pos() and not game_view.game.can_move():
                selected_pos = input_handler.get_selected_pos()
                piece = game_view.game.board.get_piece(*selected_pos)
                if piece and piece.shape == 'square':
                    up_btn.handle_event(event)
                    down_btn.handle_event(event)
                    left_btn.handle_event(event)
                    right_btn.handle_event(event)
        
        # Update game state
        game_view.update()
        
        # Handle AI turn (non-blocking)
        current_time = pygame.time.get_ticks()
        if game_view.is_ai_turn() and not show_dialog:
            if ai_move_timer == 0:
                ai_move_timer = current_time + AI_MOVE_DELAY
            
            if current_time >= ai_move_timer:
                game_view.execute_ai_turn()
                ai_move_timer = current_time + AI_MOVE_DELAY
        else:
            ai_move_timer = 0
        
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
        status_panel.draw(screen, game_view.game, game_view)
        
        # Draw buttons
        new_game_btn.draw(screen)
        
        # Draw mode buttons with highlighting
        pvp_color = (100, 149, 237) if game_view.game_mode == 'pvp' else (70, 130, 180)
        pvcpu_color = (255, 99, 71) if game_view.game_mode == 'pvcpu' else (205, 92, 92)
        pvp_btn.color = pvp_color
        pvcpu_btn.color = pvcpu_color
        pvp_btn.draw(screen)
        pvcpu_btn.draw(screen)
        
        # Draw mode label (Removed to declutter)
        
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
            
            if dialog_mode == 'ai_model_select':
                dialog_width = 300
                dialog_height = 60 + len(model_buttons) * 45
                dialog_x = (WINDOW_WIDTH - dialog_width) // 2
                dialog_y = 250
                
                dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_width, dialog_height)
                pygame.draw.rect(screen, (40, 44, 52), dialog_rect)
                pygame.draw.rect(screen, (100, 100, 100), dialog_rect, 2)
                
                title = small_font.render("Select AI Model:", True, TEXT_COLOR)
                title_rect = title.get_rect(center=(dialog_x + dialog_width//2, dialog_y + 25))
                screen.blit(title, title_rect)
                
                for _, btn in model_buttons:
                    btn.draw(screen)
            else:
                # Dialog box
                dialog_rect = pygame.Rect(250, 250, 400, 150)
                pygame.draw.rect(screen, (50, 50, 50), dialog_rect)
                pygame.draw.rect(screen, (255, 255, 255), dialog_rect, 2)
                
                # Text
                if dialog_mode == 'save':
                    mode_text = "Save"
                    prompt_text = small_font.render(f"{mode_text} game - Enter filename:", True, TEXT_COLOR)
                elif dialog_mode == 'load':
                    mode_text = "Load"
                    prompt_text = small_font.render(f"{mode_text} game - Enter filename:", True, TEXT_COLOR)
                else:  # ai_model
                    mode_text = "AI Model"
                    prompt_text = small_font.render(f"Enter AI model path:", True, TEXT_COLOR)
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
