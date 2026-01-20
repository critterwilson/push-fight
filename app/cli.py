"""Enhanced CLI interface for Push Fight game."""

import sys
from app.engine.game_state import GameState
from app.storage import save_game, load_game, list_saves


# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Text colors
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Background colors
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    
    # Piece colors
    WHITE_PIECE = '\033[97m'  # Bright white
    BROWN_PIECE = '\033[33m'  # Yellow/brown
    ANCHOR = '\033[91m'  # Bright red
    KILL_ZONE = '\033[41m\033[97m'  # Red background, white text


# Cache color support check
_COLOR_SUPPORT = None

def supports_color():
    """Check if terminal supports color (cached)."""
    global _COLOR_SUPPORT
    if _COLOR_SUPPORT is None:
        _COLOR_SUPPORT = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return _COLOR_SUPPORT


def colorize(text, color_code):
    """Apply color to text if terminal supports it."""
    if supports_color():
        return f"{color_code}{text}{Colors.RESET}"
    return text


def print_board(game, highlight_positions=None, valid_moves=None):
    """Print the game board with enhanced visualization (optimized)."""
    highlight_positions = highlight_positions or set()
    valid_moves = valid_moves or set()
    
    # Cache anchor position
    anchor_pos = game.board.anchor_pos
    has_anchor = anchor_pos[0] is not None
    
    # Build board using list for efficiency
    lines = []
    header = "   " + " ".join([f"{i:2}" for i in range(4)])
    lines.append(colorize(header, Colors.BOLD))
    
    for y in range(10):
        row_parts = [f"{y:2} "]
        for x in range(4):
            if game.board.grid[y][x] == -1:
                # Kill zone
                cell = colorize("##", Colors.KILL_ZONE)
            else:
                piece = game.board.get_piece(y, x)
                if piece:
                    # Determine piece color
                    team_color = Colors.WHITE_PIECE if piece.team == "white" else Colors.BROWN_PIECE
                    shape_char = "S" if piece.shape == "square" else "R"
                    
                    # Check if anchored
                    is_anchor = has_anchor and (y, x) == anchor_pos
                    anchor_marker = "*" if is_anchor else " "
                    piece_str = f"{shape_char}{anchor_marker}"
                    
                    # Apply colors
                    if is_anchor:
                        cell = colorize(piece_str, Colors.ANCHOR + Colors.BOLD)
                    else:
                        cell = colorize(piece_str, team_color)
                else:
                    # Empty space - highlight if in valid moves
                    if (y, x) in valid_moves:
                        cell = colorize("· ", Colors.GREEN)
                    elif (y, x) in highlight_positions:
                        cell = colorize("· ", Colors.CYAN)
                    else:
                        cell = ". "
            
            row_parts.append(cell)
            row_parts.append(" ")
        lines.append("".join(row_parts))
    
    # Print all at once
    print("\n".join(lines))
    print()


def print_status(game):
    """Print current game status."""
    print("\n" + "=" * 50)
    if game.game_over:
        winner_color = Colors.GREEN if game.winner else ""
        print(colorize(f"GAME OVER! WINNER: {game.winner.upper() if game.winner else 'DRAW'}", 
                       winner_color + Colors.BOLD))
    else:
        current_color = Colors.WHITE_PIECE if game.current_player == "white" else Colors.BROWN_PIECE
        print(colorize(f"{game.current_player.upper()}'S TURN", current_color + Colors.BOLD))
        print(f"Moves made this turn: {game.moves_made}/2")
        if game.push_completed:
            print(colorize("Push completed - turn will end", Colors.YELLOW))
    print("=" * 50)


def parse_coords(input_str):
    """Parse coordinate input in various formats: 'y,x', 'y x', or separate prompts."""
    input_str = input_str.strip()
    
    # Try comma-separated
    if ',' in input_str:
        parts = input_str.split(',')
        if len(parts) == 2:
            try:
                return int(parts[0].strip()), int(parts[1].strip())
            except ValueError:
                return None
    
    # Try space-separated
    if ' ' in input_str:
        parts = input_str.split()
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1])
            except ValueError:
                return None
    
    # Single number - return as row, will need column
    try:
        return int(input_str), None
    except ValueError:
        return None


def get_direction(prompt="Direction (w/s/a/d): "):
    """Get direction input from user (simplified prompt)."""
    direction_input = input(prompt).strip().lower()
    
    direction_map = {
        'w': (-1, 0),  # Up
        's': (1, 0),   # Down
        'a': (0, -1),  # Left
        'd': (0, 1),   # Right
        '↑': (-1, 0), 'up': (-1, 0),
        '↓': (1, 0), 'down': (1, 0),
        '←': (0, -1), 'left': (0, -1),
        '→': (0, 1), 'right': (0, 1),
    }
    
    if direction_input in direction_map:
        return direction_map[direction_input]
    else:
        print(colorize("Invalid! Use w/s/a/d", Colors.RED))
        return None


def move_piece(game):
    """Handle moving a piece with quick coordinate input."""
    print(colorize("Move: Enter 'y,x' for piece, then destination (or 'q' to cancel)", Colors.BOLD))
    
    # Get source coordinates (allow combined input)
    source_input = input("From (y,x): ").strip().lower()
    if source_input == 'q' or source_input == '':
        return False
    
    coords = parse_coords(source_input)
    if coords is None:
        print(colorize("Invalid format! Use 'y,x' or 'y x'", Colors.RED))
        return False
    
    start_y, start_x = coords
    
    # If only row provided, ask for column
    if start_x is None:
        try:
            start_x = int(input("Col: "))
        except ValueError:
            print(colorize("Invalid input!", Colors.RED))
            return False
    
    piece = game.board.get_piece(start_y, start_x)
    
    # Validate piece exists and belongs to current player
    if not piece or piece.team != game.current_player:
        print(colorize("Invalid piece! Must be one of your pieces.", Colors.RED))
        return False
    
    # Get valid moves using BFS
    valid_moves = game.board.get_valid_moves(start_y, start_x)
    
    if not valid_moves:
        print(colorize("No valid moves for this piece!", Colors.RED))
        return False
    
    # Show board with valid moves highlighted (only if needed)
    if len(valid_moves) > 1:
        print_board(game, highlight_positions={(start_y, start_x)}, valid_moves=valid_moves)
    
    # Get destination (allow combined input)
    dest_input = input("To (y,x): ").strip()
    coords = parse_coords(dest_input)
    if coords is None:
        print(colorize("Invalid format! Use 'y,x' or 'y x'", Colors.RED))
        return False
    
    dest_y, dest_x = coords
    
    # If only row provided, ask for column
    if dest_x is None:
        try:
            dest_x = int(input("Col: "))
        except ValueError:
            print(colorize("Invalid input!", Colors.RED))
            return False
    
    if (dest_y, dest_x) not in valid_moves:
        print(colorize("Invalid destination!", Colors.RED))
        return False
    
    # Move the piece
    game.board.pieces[start_y][start_x] = None
    game.board.pieces[dest_y][dest_x] = piece
    print(colorize(f"Moved ({start_y},{start_x}) → ({dest_y},{dest_x})", Colors.GREEN))
    return True


def push_piece(game):
    """Handle push phase with quick input."""
    print(colorize("Push: Enter square piece (y,x) and direction (w/s/a/d)", Colors.BOLD))
    push_successful = False
    
    while not push_successful:
        # Get piece coordinates (allow combined input)
        piece_input = input("Square piece (y,x): ").strip().lower()
        if piece_input == 'h':
            print("Push with square piece. Avoid anchor & side rails.")
            continue
        
        coords = parse_coords(piece_input)
        if coords is None:
            print(colorize("Invalid format! Use 'y,x'", Colors.RED))
            continue
        
        push_y, push_x = coords
        
        # If only row provided, ask for column
        if push_x is None:
            try:
                push_x = int(input("Col: "))
            except ValueError:
                print(colorize("Invalid input!", Colors.RED))
                continue
        
        # Get direction (simplified prompt)
        direction = get_direction("Direction (w/s/a/d): ")
        if direction is None:
            continue
        
        if game.perform_push(push_y, push_x, direction):
            push_successful = True
            print(colorize("Push successful!", Colors.GREEN))
            print_board(game)
            
            # Check for game over
            game.check_game_over()
            
            if game.game_over:
                break
            
            # Switch turns
            game.switch_turn()
        else:
            print(colorize("Invalid push! Try again.", Colors.RED))


def show_menu():
    """Show main menu options."""
    print("\n" + colorize("Commands:", Colors.BOLD))
    print("  q - Quit game")
    print("  s - Save game")
    print("  l - Load game")
    print("  n - New game")
    print("  h - Show this help")


def handle_command(game, command):
    """Handle menu commands."""
    command = command.strip().lower()
    
    if command == 'q':
        print(colorize("Thanks for playing!", Colors.CYAN))
        return False
    elif command == 's':
        filename = input("Save filename (without .json): ").strip()
        if filename:
            try:
                save_path = save_game(game, filename)
                print(colorize(f"Game saved to {save_path}", Colors.GREEN))
            except Exception as e:
                print(colorize(f"Error saving game: {e}", Colors.RED))
        return True
    elif command == 'l':
        saves = list_saves()
        if not saves:
            print(colorize("No saved games found.", Colors.YELLOW))
            return True
        
        print("\nAvailable saves:")
        for i, save in enumerate(saves, 1):
            print(f"  {i}. {save}")
        
        try:
            choice = input("Enter save number or filename: ").strip()
            # Try as number first
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(saves):
                    filename = saves[idx]
                else:
                    print(colorize("Invalid selection.", Colors.RED))
                    return True
            else:
                filename = choice
            
            loaded_game = load_game(filename)
            game.__dict__.update(loaded_game.__dict__)
            print(colorize(f"Game loaded: {filename}", Colors.GREEN))
        except FileNotFoundError:
            print(colorize("Save file not found.", Colors.RED))
        except Exception as e:
            print(colorize(f"Error loading game: {e}", Colors.RED))
        return True
    elif command == 'n':
        confirm = input("Start new game? (y/n): ").strip().lower()
        if confirm == 'y':
            new_game = GameState.create_initial_game()
            game.__dict__.update(new_game.__dict__)
            print(colorize("New game started!", Colors.GREEN))
        return True
    elif command == 'h':
        show_menu()
        return True
    else:
        print(colorize(f"Unknown command: {command}", Colors.RED))
        return True


def play_game():
    """Main game loop with enhanced CLI."""
    game = GameState.create_initial_game()
    
    print("\n" + colorize("=" * 50, Colors.BOLD))
    print(colorize("WELCOME TO PUSH FIGHT!", Colors.BOLD + Colors.CYAN))
    print(colorize("=" * 50, Colors.BOLD))
    print("\nRules:")
    print("- White team goes first")
    print("- Each turn: Make 0-2 moves, then mandatory push")
    print("- Win by pushing opponent's piece off the board")
    print("\nCommands: q=quit, s=save, l=load, n=new game, h=help")
    print(colorize("=" * 50, Colors.BOLD))
    
    while not game.game_over:
        print_board(game)
        print_status(game)
        
        # Check for game over conditions (0 Square pieces)
        game.check_game_over()
        if game.game_over:
            break
        
        # Check if player is trapped (no legal pushes)
        if not game.has_legal_push():
            print(colorize(f"{game.current_player.upper()} has no legal pushes! Game Over.", Colors.RED))
            game.game_over = True
            game.winner = 'brown' if game.current_player == 'white' else 'white'
            break
        
        # Move Phase: Up to 2 moves (optional - can skip)
        while game.can_move():
            # Default to skip if just pressing Enter - moves are optional
            action = input(f"\nMove? (Enter=skip, y=move, q/s/l/h=commands): ").strip().lower()
            
            # Quick command check
            if action in ['q', 's', 'l', 'h']:
                if not handle_command(game, action):
                    return  # Quit
                continue
            
            # Empty input or 'n' means skip moves
            if action == '' or action == 'n':
                print(colorize("Skipping moves - proceeding to push phase", Colors.YELLOW))
                break  # Skip remaining moves
            
            # Check if it's a coordinate input (quick move)
            if ',' in action or ' ' in action:
                # User entered coordinates directly - try to parse as move
                coords = parse_coords(action)
                if coords and coords[1] is not None:
                    # They gave us both coordinates, treat as piece selection
                    # This is a shortcut - we'll need destination too
                    print(colorize("Quick move mode - enter destination (y,x):", Colors.CYAN))
                    # For now, fall through to normal move
                    action = 'y'
            
            if action == 'y':
                if move_piece(game):
                    game.moves_made += 1
                    # Only print board if there are more moves available
                    if game.can_move():
                        print_board(game)
                else:
                    print(colorize("Move failed. Try again.", Colors.YELLOW))
            else:
                print(colorize("Invalid input. Press Enter to skip, 'y' to move, or q/s/l/h for commands", Colors.RED))
        
        if game.game_over:
            break
        
        # Mandatory Push Phase
        push_piece(game)
    
    # Game Over
    print("\n" + colorize("=" * 50, Colors.BOLD))
    winner_color = Colors.GREEN if game.winner else Colors.YELLOW
    print(colorize(f"GAME OVER! WINNER: {game.winner.upper() if game.winner else 'DRAW'}", 
                   winner_color + Colors.BOLD))
    print(colorize("=" * 50, Colors.BOLD))
    print_board(game)
    
    # Ask if player wants to play again
    play_again = input("\nPlay again? (y/n): ").strip().lower()
    if play_again == 'y':
        play_game()


if __name__ == "__main__":
    try:
        play_game()
    except KeyboardInterrupt:
        print("\n\n" + colorize("Game interrupted. Thanks for playing!", Colors.CYAN))
        sys.exit(0)
