"""
PyGame desktop application entry point for Push Fight.

Wires together the board renderer, input handler, game view (controller),
UI buttons, status panel, and the RAG referee chat overlay into a single
60 FPS game loop.

Layout (900 × 700 window):
  - Left side: 10×4 board rendered at (100, 50) with 60 px cells.
  - Right side (x ≥ 500): status panel, action buttons, direction pad,
    save/load dialogs.
  - Centre overlay: chat panel for the AI referee (toggled via button).

Run directly::

    python -m app.pygame_ui.main
"""

import pygame
import sys
import os
from app.pygame_ui.game_view import GameView
from app.pygame_ui.board_renderer import BoardRenderer
from app.pygame_ui.input_handler import InputHandler
from app.pygame_ui.ui_components import Button, StatusPanel
from app.pygame_ui.chat_overlay import ChatOverlay
from app.rag.ai_interface import AIInterface


# ── Window / layout constants ────────────────────────────────────────────
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 700
BOARD_X = 100        # Board top-left X
BOARD_Y = 50         # Board top-left Y
CELL_SIZE = 60       # Pixels per cell
FPS = 60

# ── Colour palette ───────────────────────────────────────────────────────
BACKGROUND = (20, 24, 30)
TEXT_COLOR = (255, 255, 255)


def main():
    """
    Initialise PyGame, build UI components, and run the main event/render loop.

    The loop follows a standard structure:
      1. **Event handling** — mouse clicks, keyboard, chat overlay events.
      2. **State updates** — game-over checks, AI turn scheduling, chat queue.
      3. **Rendering** — board, buttons, status, dialogs, chat overlay.
    """
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
    
    # RAG Referee
    ai_interface = AIInterface()
    chat_overlay = ChatOverlay(WINDOW_WIDTH, WINDOW_HEIGHT)
    ask_referee_btn = Button(500, 580, 150, 40, "Ask Referee", (100, 80, 140))

    # ── Game loop state ──────────────────────────────────────────────────
    running = True
    show_dialog = False
    dialog_mode = None  # 'save', 'load', or 'ai_model'
    dialog_filename = ""
    model_buttons = []

    # ── AI turn timing ───────────────────────────────────────────────────
    ai_move_timer = 0
    AI_MOVE_DELAY = 600  # ms between AI actions
    
    # ==========================================================================
    # Main Game Loop
    # ==========================================================================
    while running:
        # ----------------------------------------------------------------------
        # 1. Event Handling
        # ----------------------------------------------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            # Chat overlay is modal: it consumes all events when visible
            elif chat_overlay.visible:
                chat_overlay.handle_event(event)
                continue

            # --- Mouse clicks ---
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    # Dialogs are modal: they consume clicks before main UI
                    if show_dialog and dialog_mode == 'ai_model_select':
                        for path, btn in model_buttons:
                            if btn.handle_event(event):
                                game_view.set_game_mode('pvcpu', path)
                                show_dialog = False
                                dialog_mode = None
                                break
                    
                    # --- Main UI buttons ---
                    elif not show_dialog and new_game_btn.handle_event(event):
                        game_view.new_game()
                        input_handler.clear_selection()
                    elif not show_dialog and pvp_btn.handle_event(event):
                        game_view.set_game_mode('pvp')
                        input_handler.clear_selection()
                    elif not show_dialog and pvcpu_btn.handle_event(event):
                        # When PvCPU is selected, show a model selection dialog
                        models_dir = "models"
                        if not os.path.exists(models_dir):
                            try:
                                os.makedirs(models_dir)
                            except OSError:
                                pass
                        
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
                                name = model.replace(".zip", "")
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
                            dialog_filename = "models/easy"
                    elif not show_dialog and save_btn.handle_event(event):
                        show_dialog = True
                        dialog_mode = 'save'
                        dialog_filename = ""
                    elif not show_dialog and load_btn.handle_event(event):
                        show_dialog = True
                        dialog_mode = 'load'
                        dialog_filename = ""
                    elif not show_dialog and ask_referee_btn.handle_event(event):
                        chat_overlay.show()
                    elif not show_dialog and skip_moves_btn.handle_event(event):
                        # Allow player to skip remaining moves and go to push phase
                        if game_view.game.can_move():
                            game_view.set_message("Moves skipped - proceeding to push phase")
                            game_view.game.moves_made = 2
                    
                    # --- Push direction buttons ---
                    elif not show_dialog and input_handler.get_selected_pos() and not game_view.game.can_move():
                        selected_pos = input_handler.get_selected_pos()
                        piece = game_view.game.board.get_piece(*selected_pos)
                        if piece and piece.shape == 'square':
                            direction = None
                            if up_btn.handle_event(event): direction = (-1, 0)
                            elif down_btn.handle_event(event): direction = (1, 0)
                            elif left_btn.handle_event(event): direction = (0, -1)
                            elif right_btn.handle_event(event): direction = (0, 1)
                            
                            if direction:
                                if game_view.push_piece(selected_pos, direction):
                                    input_handler.clear_selection()
                    
                    # --- Board clicks for piece selection/movement ---
                    else:
                        if not show_dialog and not game_view.is_ai_turn():
                            action = input_handler.handle_click(event.pos, game_view.game)
                            if action:
                                if action['type'] == 'move':
                                    game_view.move_piece(action['from'], action['to'])
                                    input_handler.clear_selection()
            
            # --- Keyboard input ---
            elif event.type == pygame.KEYDOWN:
                # Game input (e.g. keyboard-based push)
                if not show_dialog and not game_view.is_ai_turn():
                    action = input_handler.handle_key(event.key, game_view.game)
                    if action and action['type'] == 'push':
                        game_view.push_piece(action['piece'], action['direction'])
                        input_handler.clear_selection()
                
                # Dialog text input
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
                    elif event.key == pygame.K_ESCAPE:
                        show_dialog = False
                    elif event.key == pygame.K_BACKSPACE:
                        dialog_filename = dialog_filename[:-1]
                    else:
                        if event.unicode.isprintable():
                            dialog_filename += event.unicode
            
            # --- Mouse hover (for button pseudo-classes) ---
            if show_dialog and dialog_mode == 'ai_model_select':
                for _, btn in model_buttons:
                    btn.handle_event(event)
            else:
                # Main UI buttons
                new_game_btn.handle_event(event)
                pvp_btn.handle_event(event)
                pvcpu_btn.handle_event(event)
                save_btn.handle_event(event)
                load_btn.handle_event(event)
                skip_moves_btn.handle_event(event)
                ask_referee_btn.handle_event(event)
            
            # Direction buttons
            if not show_dialog and input_handler.get_selected_pos() and not game_view.game.can_move():
                selected_pos = input_handler.get_selected_pos()
                piece = game_view.game.board.get_piece(*selected_pos)
                if piece and piece.shape == 'square':
                    up_btn.handle_event(event)
                    down_btn.handle_event(event)
                    left_btn.handle_event(event)
                    right_btn.handle_event(event)
        
        # ----------------------------------------------------------------------
        # 2. State Updates
        # ----------------------------------------------------------------------
        game_view.update()

        # Update chat overlay (drains answer queue from RAG, handles animations)
        chat_overlay.referee_ready = ai_interface.is_ready
        chat_overlay.referee_error = ai_interface.loading_error
        chat_overlay.update()

        # Dispatch a pending question to the RAG referee (non-blocking)
        if chat_overlay.pending_question:
            question = chat_overlay.pending_question
            chat_overlay.pending_question = None
            ai_interface.ask_question(
                game_view.game, question, chat_overlay.receive_answer
            )
        
        # --- AI turn logic ---
        # A timer adds a small delay between AI moves to make them human-readable
        current_time = pygame.time.get_ticks()
        if game_view.is_ai_turn() and not show_dialog:
            if ai_move_timer == 0:
                ai_move_timer = current_time + AI_MOVE_DELAY
            
            if current_time >= ai_move_timer:
                game_view.execute_ai_turn()
                ai_move_timer = current_time + AI_MOVE_DELAY
        else:
            ai_move_timer = 0
        
        # ----------------------------------------------------------------------
        # 3. Rendering
        # ----------------------------------------------------------------------
        screen.fill(BACKGROUND)
        
        # Board with pieces, highlights, and anchor
        selected_pos = input_handler.get_selected_pos()
        valid_moves = input_handler.get_valid_moves()
        board_renderer.draw_board(
            screen, game_view.game, 
            selected_pos=selected_pos,
            valid_moves=valid_moves
        )
        
        # Right-hand panel with status and controls
        status_panel.draw(screen, game_view.game, game_view)
        
        # --- Main buttons ---
        new_game_btn.draw(screen)
        
        pvp_color = (100, 149, 237) if game_view.game_mode == 'pvp' else (70, 130, 180)
        pvcpu_color = (255, 99, 71) if game_view.game_mode == 'pvcpu' else (205, 92, 92)
        pvp_btn.color = pvp_color
        pvcpu_btn.color = pvcpu_color
        pvp_btn.draw(screen)
        pvcpu_btn.draw(screen)
        
        save_btn.draw(screen)
        load_btn.draw(screen)
        ask_referee_btn.draw(screen)
        
        # --- Phase-dependent controls ---
        # Skip moves button (only during move phase)
        if game_view.game.can_move() and not game_view.game.game_over:
            skip_moves_btn.draw(screen)
        
        # Direction buttons for push phase
        selected_pos = input_handler.get_selected_pos()
        if selected_pos and not game_view.game.can_move() and not game_view.game.game_over:
            piece = game_view.game.board.get_piece(*selected_pos)
            if piece and piece.shape == 'square' and piece.team == game_view.game.current_player:
                label_text = small_font.render("Push Direction:", True, TEXT_COLOR)
                screen.blit(label_text, (direction_btn_x, direction_btn_y - 25))
                
                up_btn.draw(screen)
                down_btn.draw(screen)
                left_btn.draw(screen)
                right_btn.draw(screen)
        
        # --- Overlays and status messages ---
        # Yellow status message at bottom-left
        message = game_view.get_message()
        if message:
            text_surface = small_font.render(message, True, (255, 255, 0))
            screen.blit(text_surface, (50, WINDOW_HEIGHT - 40))
        
        # Modal dialogs for save/load/AI selection
        if show_dialog:
            # Semi-transparent backdrop
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
                # Text input dialog for save/load
                dialog_rect = pygame.Rect(250, 250, 400, 150)
                pygame.draw.rect(screen, (50, 50, 50), dialog_rect)
                pygame.draw.rect(screen, (255, 255, 255), dialog_rect, 2)
                
                prompt_text = small_font.render(f"Enter filename for {dialog_mode}:", True, TEXT_COLOR)
                screen.blit(prompt_text, (dialog_rect.x + 20, dialog_rect.y + 20))
                
                filename_text = small_font.render(dialog_filename + "_", True, TEXT_COLOR)
                screen.blit(filename_text, (dialog_rect.x + 20, dialog_rect.y + 60))
                
                hint_text = small_font.render("Enter to confirm, Esc to cancel", True, (150, 150, 150))
                screen.blit(hint_text, (dialog_rect.x + 20, dialog_rect.y + 100))
        
        # Chat overlay is always rendered last so it's on top
        chat_overlay.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)
    
    # ==========================================================================
    # Shutdown
    # ==========================================================================
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
