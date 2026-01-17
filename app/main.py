import argparse
import sys
from app.engine.game_state import GameState


def print_board(game):
    """Prints the game board with pieces and grid layout."""
    print("\n   " + " ".join([str(i) for i in range(4)]))
    for y in range(10):
        row_str = f"{y:2} "
        for x in range(4):
            if game.board.grid[y][x] == -1:
                row_str += "## "  # Kill zone
            else:
                piece = game.board.get_piece(y, x)
                if piece:
                    # Show piece: W=white, B=brown, S=square, R=round
                    team_char = "W" if piece.team == "white" else "B"
                    shape_char = "S" if piece.shape == "square" else "R"
                    anchor_marker = "*" if (y, x) == game.board.anchor_pos else " "
                    row_str += f"{team_char}{shape_char}{anchor_marker} "
                else:
                    row_str += ".  "  # Empty space
        print(row_str)
    print()


def get_direction():
    """Gets direction input from user and returns (dy, dx) tuple."""
    print("Direction: w=up, s=down, a=left, d=right")
    direction_input = input("Enter direction: ").strip().lower()
    
    direction_map = {
        'w': (-1, 0),  # Up
        's': (1, 0),   # Down
        'a': (0, -1),  # Left
        'd': (0, 1)    # Right
    }
    
    if direction_input in direction_map:
        return direction_map[direction_input]
    else:
        print("Invalid direction! Use w, s, a, or d.")
        return None


def move_piece(game):
    """Handles moving a piece using BFS to find valid destinations."""
    print("\n--- Move Phase ---")
    print("Select a piece to move:")
    try:
        start_y = int(input("Piece Row: "))
        start_x = int(input("Piece Col: "))
    except ValueError:
        print("Invalid input!")
        return False
    
    piece = game.board.get_piece(start_y, start_x)
    
    # Validate piece exists and belongs to current player
    if not piece or piece.team != game.current_player:
        print("Invalid piece! Must be one of your pieces.")
        return False
    
    # Get valid moves using BFS
    valid_moves = game.board.get_valid_moves(start_y, start_x)
    
    if not valid_moves:
        print("No valid moves for this piece!")
        return False
    
    print(f"Valid destinations: {sorted(valid_moves)}")
    try:
        dest_y = int(input("Destination Row: "))
        dest_x = int(input("Destination Col: "))
    except ValueError:
        print("Invalid input!")
        return False
    
    if (dest_y, dest_x) not in valid_moves:
        print("Invalid destination! Must be a connected empty space.")
        return False
    
    # Move the piece
    game.board.pieces[start_y][start_x] = None
    game.board.pieces[dest_y][dest_x] = piece
    print(f"Moved piece from ({start_y}, {start_x}) to ({dest_y}, {dest_x})")
    return True


def play_game():
    """Main game loop."""
    game = GameState.create_initial_game()
    
    print("=" * 50)
    print("WELCOME TO PUSH FIGHT!")
    print("=" * 50)
    print("\nRules:")
    print("- White team goes first")
    print("- Each turn: Make 0-2 moves, then mandatory push")
    print("- Win by pushing opponent's piece off the board")
    print("=" * 50)
    
    while not game.game_over:
        print_board(game)
        print(f"\n--- {game.current_player.upper()}'S TURN ---")
        print(f"Moves made this turn: {game.moves_made}/2")
        
        # Check if player is trapped (no legal pushes) [cite: 51]
        if not game.has_legal_push():
            print(f"{game.current_player.upper()} has no legal pushes! Game Over.")
            # The opponent wins
            game.game_over = True
            game.winner = 'brown' if game.current_player == 'white' else 'white'
            break
        
        # Move Phase: Up to 2 moves [cite: 24, 29]
        while game.can_move():
            action = input("\nMove a piece? (y/n): ").strip().lower()
            if action == 'y':
                if move_piece(game):
                    game.moves_made += 1
                    print_board(game)
                else:
                    print("Move failed. Try again.")
            else:
                break  # Player chooses to skip remaining moves
        
        # Mandatory Push Phase [cite: 30, 31, 51]
        print("\n--- Mandatory Push Phase ---")
        push_successful = False
        
        while not push_successful:
            try:
                push_y = int(input("Square Piece Row: "))
                push_x = int(input("Square Piece Col: "))
            except ValueError:
                print("Invalid input! Enter numbers.")
                continue
            
            direction = get_direction()
            if direction is None:
                continue
            
            if game.perform_push(push_y, push_x, direction):
                push_successful = True
                print_board(game)
                
                # Check for victory
                if game.game_over:
                    break
                
                # Switch turns
                game.switch_turn()
            else:
                print("Invalid push! Try again.")
                print("Remember: Must push with your square piece, avoid anchor, avoid side rails.")
    
    # Game Over
    print("\n" + "=" * 50)
    print(f"GAME OVER! WINNER: {game.winner.upper()}")
    print("=" * 50)
    print_board(game)


def run_web_server(host='0.0.0.0', port=5000, debug=False):
    """Run the Flask web server."""
    from app.web.app import create_app
    
    app = create_app()
    print(f"Starting Flask web server on http://{host}:{port}")
    print(f"API endpoints available at http://{host}:{port}/api/")
    print("Press Ctrl+C to stop the server")
    app.run(host=host, port=port, debug=debug)


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description='Push Fight Game - Play in CLI or start web server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Play in CLI mode
  python -m app.main

  # Start web server
  python -m app.main --web

  # Start web server on custom host/port
  python -m app.main --web --host 127.0.0.1 --port 8080

  # Start web server in debug mode
  python -m app.main --web --debug
        """
    )
    
    parser.add_argument(
        '--web',
        action='store_true',
        help='Start Flask web server instead of CLI game'
    )
    
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind web server to (default: 0.0.0.0)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to bind web server to (default: 5000)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable Flask debug mode'
    )
    
    args = parser.parse_args()
    
    if args.web:
        run_web_server(host=args.host, port=args.port, debug=args.debug)
    else:
        play_game()


if __name__ == "__main__":
    main()
