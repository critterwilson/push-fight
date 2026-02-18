"""Play against a trained RL agent."""

import os
import json
import datetime
import argparse
from app.engine.game_state import GameState
from app.rl.agent import PushFightAgent
from app.cli import print_board, parse_coords, get_direction, colorize, Colors


def execute_ai_action(game_state, action):
    """
    Execute AI action on game state.
    
    Args:
        game_state: Current GameState
        action: Action dictionary
        
    Returns:
        bool: True if action was successful
    """
    if action is None:
        return False
    
    if action['type'] == 'move':
        from_y, from_x = action['from']
        to_y, to_x = action['to']
        
        success, _ = game_state.perform_move((from_y, from_x), (to_y, to_x))
        return success
    
    elif action['type'] == 'push':
        y, x = action['piece']
        direction = action['direction']
        success = game_state.perform_push(y, x, direction)
        if success and game_state.push_completed:
            game_state.switch_turn()
        return success
    
    return False


def human_move(game_state):
    """Get and execute a human move."""
    print(colorize("\n=== YOUR MOVE ===", Colors.BOLD))
    
    # Move phase
    while game_state.can_move():
        print_board(game_state)
        action = input(f"\nMove? (Enter=skip, y=move, q=quit): ").strip().lower()
        
        if action == 'q':
            return False
        
        if action == '' or action == 'n':
            print(colorize("Skipping moves - proceeding to push phase", Colors.YELLOW))
            break
        
        if action == 'y':
            # Get source
            source_input = input("From (y,x): ").strip()
            if source_input == 'q':
                return False
            
            coords = parse_coords(source_input)
            if coords is None:
                print(colorize("Invalid format! Use 'y,x'", Colors.RED))
                continue
            
            start_y, start_x = coords
            if start_x is None:
                try:
                    start_x = int(input("Col: "))
                except ValueError:
                    print(colorize("Invalid input!", Colors.RED))
                    continue
            
            piece = game_state.board.get_piece(start_y, start_x)
            if not piece or piece.team != game_state.current_player:
                print(colorize("Invalid piece! Must be one of your pieces.", Colors.RED))
                continue
            
            valid_moves = game_state.board.get_valid_moves(start_y, start_x)
            if not valid_moves:
                print(colorize("No valid moves for this piece!", Colors.RED))
                continue
            
            # Get destination
            dest_input = input("To (y,x): ").strip()
            coords = parse_coords(dest_input)
            if coords is None:
                print(colorize("Invalid format! Use 'y,x'", Colors.RED))
                continue
            
            dest_y, dest_x = coords
            if dest_x is None:
                try:
                    dest_x = int(input("Col: "))
                except ValueError:
                    print(colorize("Invalid input!", Colors.RED))
                    continue
            
            if (dest_y, dest_x) not in valid_moves:
                print(colorize("Invalid destination!", Colors.RED))
                continue
            
            # Execute move
            success, msg = game_state.perform_move((start_y, start_x), (dest_y, dest_x))
            if success:
                print(colorize("Move successful!", Colors.GREEN))
            else:
                print(colorize(f"Move failed: {msg}", Colors.RED))
    
    # Push phase
    if game_state.game_over:
        return True
    
    print_board(game_state)
    print(colorize("\n=== PUSH PHASE ===", Colors.BOLD))
    
    while True:
        piece_input = input("Square piece (y,x): ").strip().lower()
        if piece_input == 'q':
            return False
        
        coords = parse_coords(piece_input)
        if coords is None:
            print(colorize("Invalid format! Use 'y,x'", Colors.RED))
            continue
        
        push_y, push_x = coords
        if push_x is None:
            try:
                push_x = int(input("Col: "))
            except ValueError:
                print(colorize("Invalid input!", Colors.RED))
                continue
        
        direction = get_direction("Direction (w/s/a/d): ")
        if direction is None:
            continue
        
        if game_state.perform_push(push_y, push_x, direction):
            print(colorize("Push successful!", Colors.GREEN))
            game_state.check_game_over()
            if game_state.push_completed:
                game_state.switch_turn()
            return True
        else:
            print(colorize("Invalid push! Try again.", Colors.RED))


def ai_turn(agent, game_state):
    """Execute AI's turn. Guarantees the turn switches when done."""
    print(colorize("\n=== AI'S TURN ===", Colors.BOLD))
    print(colorize("AI is thinking...", Colors.CYAN))

    # Move phase (up to 2 moves)
    move_attempts = 0
    while game_state.can_move() and move_attempts < 5:
        action = agent.get_action(game_state)
        move_attempts += 1
        if action and action['type'] == 'move':
            from_y, from_x = action['from']
            to_y, to_x = action['to']
            if execute_ai_action(game_state, action):
                print(colorize(f"AI moved piece from ({from_y},{from_x}) to ({to_y},{to_x})", Colors.CYAN))
                print_board(game_state)
            else:
                break
        else:
            break

    if game_state.game_over:
        return

    # Push phase (mandatory)
    print(colorize("AI is pushing...", Colors.CYAN))
    dir_names = {(-1, 0): 'up', (1, 0): 'down', (0, -1): 'left', (0, 1): 'right'}

    for attempt in range(5):
        action = agent.get_action(game_state)
        if action and action['type'] == 'push':
            y, x = action['piece']
            direction = action['direction']
            dir_name = dir_names.get(direction, 'unknown')

            if execute_ai_action(game_state, action):
                print(colorize(f"AI pushed from ({y},{x}) {dir_name}", Colors.CYAN))
                game_state.check_game_over()
                print_board(game_state)
                return
            else:
                print(colorize(f"AI push attempt {attempt+1} failed, retrying...", Colors.YELLOW))
        else:
            print(colorize(f"AI didn't return a push action (attempt {attempt+1}), retrying...", Colors.YELLOW))

    # Fallback: all attempts failed, force a random valid push
    print(colorize("AI falling back to random valid push...", Colors.YELLOW))
    import numpy as np
    agent.env.game = game_state
    agent.env.current_phase = 'push'
    valid_actions = agent.env._get_valid_actions()
    if valid_actions:
        action_idx = int(np.random.choice(valid_actions))
        phase, action_data = agent.env._decode_action(action_idx)
        if phase == 'push':
            y, x, direction = action_data
            dir_name = dir_names.get(direction, 'unknown')
            success = game_state.perform_push(y, x, direction)
            if success:
                print(colorize(f"AI pushed from ({y},{x}) {dir_name} (fallback)", Colors.CYAN))
                game_state.check_game_over()
                if game_state.push_completed:
                    game_state.switch_turn()
                print_board(game_state)
                return

    # If we still couldn't push, AI has no legal push = AI loses
    print(colorize("AI has no legal push available!", Colors.YELLOW))
    game_state.game_over = True
    opponent = 'white' if game_state.current_player == 'black' else 'black'
    game_state.winner = opponent


def save_game_log(game_state):
    """Save the game move history to a JSON file."""
    if not game_state.move_log:
        return
        
    logs_dir = "game_logs"
    if not os.path.exists(logs_dir):
        try:
            os.makedirs(logs_dir)
        except OSError:
            pass
            
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    winner_str = game_state.winner if game_state.winner else 'draw'
    filename = f"game_{timestamp}_{winner_str}.json"
    filepath = os.path.join(logs_dir, filename)
    
    data = {
        'winner': game_state.winner,
        'moves': game_state.move_log,
        'final_board': game_state.board.to_dict()
    }
    
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(colorize(f"Game log saved to {filepath}", Colors.GREEN))
    except Exception as e:
        print(colorize(f"Failed to save game log: {e}", Colors.RED))


def play_against_ai(model_path, human_team='white', difficulty='medium'):
    """
    Play a game against the AI.
    
    Args:
        model_path: Path to trained model (can be .zip file or directory)
        human_team: 'white' or 'black' (default: 'white')
        difficulty: AI difficulty (not used with trained model, but kept for compatibility)
    """
    # Handle model path - Stable-Baselines3 saves as .zip files
    original_path = model_path
    
    # If it's a directory, look for .zip file in parent directory
    if os.path.isdir(model_path):
        dir_name = os.path.basename(model_path.rstrip('/'))
        parent_dir = os.path.dirname(model_path) if os.path.dirname(model_path) else '.'
        zip_path = os.path.join(parent_dir, dir_name + ".zip")
        
        if os.path.exists(zip_path):
            model_path = zip_path
        else:
            print(colorize(f"Warning: {model_path} is a directory. Looking for .zip file...", Colors.YELLOW))
            # Try current directory
            zip_path = dir_name + ".zip"
            if os.path.exists(zip_path):
                model_path = zip_path
            else:
                print(colorize(f"Error: No .zip file found for {original_path}", Colors.RED))
                print(colorize("Stable-Baselines3 models should be .zip files", Colors.YELLOW))
                print(colorize("Try: python -m app.rl.train --train to create a model", Colors.YELLOW))
                return
    
    # If path doesn't end with .zip, try adding it
    if not model_path.endswith('.zip'):
        zip_path = model_path + ".zip"
        if os.path.exists(zip_path):
            model_path = zip_path
    
    # Load model
    if not os.path.exists(model_path):
        print(colorize(f"Error: Model not found at {model_path}", Colors.RED))
        print(colorize(f"Also checked: {original_path}", Colors.YELLOW))
    try:
        print(colorize(f"Loading model from {model_path}...", Colors.CYAN))
        agent = PushFightAgent(model_path)
        print(colorize("✓ Model loaded!", Colors.GREEN))
    except FileNotFoundError as e:
        print(colorize(f"Error: {e}", Colors.RED))
        print(colorize("Train a model first with: python -m app.rl.train --train", Colors.YELLOW))
        return
    
    # Create game
    game = GameState.create_initial_game()
    
    # Set human team
    if human_team == 'black':
        # Swap so human goes second
        game.current_player = 'black'
    
    print(colorize("\n" + "="*60, Colors.BOLD))
    print(colorize("PLAYING AGAINST AI", Colors.BOLD))
    print(colorize("="*60, Colors.BOLD))
    print(colorize(f"You are playing as: {human_team.upper()}", Colors.BOLD))
    print(colorize("="*60 + "\n", Colors.BOLD))
    
    # Game loop
    while not game.game_over:
        if game.current_player == human_team:
            # Human turn
            if not human_move(game):
                print(colorize("\nGame quit by user.", Colors.YELLOW))
                return
        else:
            # AI turn
            ai_turn(agent, game)
        
        # Check for game over
        game.check_game_over()
    
    # Game over
    print(colorize("\n" + "="*60, Colors.BOLD))
    if game.winner == human_team:
        print(colorize("🎉 YOU WIN! 🎉", Colors.GREEN + Colors.BOLD))
    else:
        print(colorize("🤖 AI WINS! 🤖", Colors.RED + Colors.BOLD))
    print(colorize("="*60, Colors.BOLD))
    save_game_log(game)
    print_board(game)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Play Push Fight against a trained AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Play as white (goes first)
  python -m app.rl.play_against_ai --model models/push_fight_ppo

  # Play as black (goes second)
  python -m app.rl.play_against_ai --model models/push_fight_ppo --team black
        """
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default='models/push_fight_ppo',
        help='Path to trained model (default: models/push_fight_ppo)'
    )
    parser.add_argument(
        '--team',
        type=str,
        choices=['white', 'black'],
        default='white',
        help='Which team you play as (default: white)'
    )
    
    args = parser.parse_args()
    
    play_against_ai(args.model, args.team)


if __name__ == "__main__":
    main()
