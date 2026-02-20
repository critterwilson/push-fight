"""Command-line interface for playing Push Fight against a trained RL agent.

This module provides an interactive terminal-based game where a human player
faces off against a trained MaskablePPO agent.  It handles:
  - Human input for move and push phases (coordinate entry with validation)
  - AI turn execution with multi-attempt fallback logic
  - Game state management and turn switching
  - Game logging to JSON files for post-game analysis

Game flow
---------
Push Fight alternates between two phases each turn:

  1. **Move phase** (optional): The player may slide up to 2 of their pieces
     to new positions on the board.  Pieces slide through empty cells (no
     jumping).  The player can skip moves entirely by pressing Enter.

  2. **Push phase** (mandatory): The player must select one of their square
     pieces and push it in a cardinal direction.  This shoves the entire
     chain of adjacent pieces in that direction.  If any piece is pushed off
     the board, that piece's team loses.

The human plays one team (white or black) and the AI plays the other.  Piece
placement (setup phase) uses the standard initial layout from
``GameState.create_initial_game()``.

AI fallback strategy
--------------------
The AI uses ``PushFightAgent.get_action()`` to predict moves and pushes.
However, since the agent was trained in a Gymnasium environment where actions
are flat integers, there can occasionally be mismatches when translating back
to the game engine's API (e.g., a predicted push that the engine rejects).

To handle this robustly, the AI has a 3-tier fallback strategy:
  1. Try the model's predicted action (up to 5 attempts for pushes).
  2. If all attempts fail, sync the env to the game state and pick a random
     valid push from the action mask.
  3. If even that fails (no legal pushes), the AI loses by forfeit.

Game logging
------------
After each game, the complete move history and final board state are saved
to ``game_logs/game_YYYYMMDD_HHMMSS_winner.json``.  This enables:
  - Post-game analysis and replay
  - Identifying common failure patterns for model improvement
  - Collecting human vs AI game data for future training
"""

import os
import json
import datetime
import argparse
from app.engine.game_state import GameState
from app.rl.agent import PushFightAgent
from app.cli import print_board, parse_coords, get_direction, colorize, Colors


def execute_ai_action(game_state, action):
    """Execute an AI-generated action on the authoritative game state.

    Translates the structured action dictionary (from ``PushFightAgent.get_action()``)
    into the appropriate game engine calls.  For push actions, also handles
    turn switching when the push is complete.

    Args:
        game_state: The current ``GameState`` instance (modified in place).
        action: Action dictionary with one of two formats:
            - ``{'type': 'move', 'from': (y, x), 'to': (y, x)}``
            - ``{'type': 'push', 'piece': (y, x), 'direction': (dy, dx)}``
            - ``None`` is handled gracefully (returns False).

    Returns:
        bool: True if the action was successfully executed on the game state,
            False otherwise (invalid action, None action, or engine rejection).
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
        # After a successful push, switch turns if the push is complete
        # (the anchor has been placed and the turn is ready to transfer).
        if success and game_state.push_completed:
            game_state.switch_turn()
        return success

    return False


def human_move(game_state):
    """Handle the human player's complete turn (move phase + push phase).

    Prompts the human for up to 2 optional moves followed by one mandatory
    push.  All inputs are validated against the game engine before execution.

    The move phase supports:
      - 'y' to make a move (then prompts for source and destination coords)
      - Enter or 'n' to skip remaining moves and proceed to push
      - 'q' to quit the game

    The push phase requires:
      - A square piece coordinate (y, x)
      - A direction (w/a/s/d for up/left/down/right)

    Args:
        game_state: The current ``GameState`` instance (modified in place).

    Returns:
        bool: True if the turn completed normally, False if the user quit.
    """
    print(colorize("\n=== YOUR MOVE ===", Colors.BOLD))

    # --- Move phase: up to 2 optional piece slides ---
    while game_state.can_move():
        print_board(game_state)
        action = input(f"\nMove? (Enter=skip, y=move, q=quit): ").strip().lower()

        if action == 'q':
            return False

        if action == '' or action == 'n':
            # Player chooses to skip remaining moves and go straight to push.
            print(colorize("Skipping moves - proceeding to push phase", Colors.YELLOW))
            break

        if action == 'y':
            # --- Get source piece coordinates ---
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

            # Validate that the selected cell contains one of the player's pieces.
            piece = game_state.board.get_piece(start_y, start_x)
            if not piece or piece.team != game_state.current_player:
                print(colorize("Invalid piece! Must be one of your pieces.", Colors.RED))
                continue

            # Check that the piece has at least one legal destination.
            valid_moves = game_state.board.get_valid_moves(start_y, start_x)
            if not valid_moves:
                print(colorize("No valid moves for this piece!", Colors.RED))
                continue

            # --- Get destination coordinates ---
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

            # Execute the validated move on the game state.
            success, msg = game_state.perform_move((start_y, start_x), (dest_y, dest_x))
            if success:
                print(colorize("Move successful!", Colors.GREEN))
            else:
                print(colorize(f"Move failed: {msg}", Colors.RED))

    # --- Push phase: mandatory push with a square piece ---
    if game_state.game_over:
        return True

    print_board(game_state)
    print(colorize("\n=== PUSH PHASE ===", Colors.BOLD))

    while True:
        # Get the square piece to push with.
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

        # Get the push direction (w=up, s=down, a=left, d=right).
        direction = get_direction("Direction (w/s/a/d): ")
        if direction is None:
            continue

        # Attempt the push and handle the result.
        if game_state.perform_push(push_y, push_x, direction):
            print(colorize("Push successful!", Colors.GREEN))
            game_state.check_game_over()
            if game_state.push_completed:
                game_state.switch_turn()
            return True
        else:
            print(colorize("Invalid push! Try again.", Colors.RED))


def ai_turn(agent, game_state):
    """Execute the AI's complete turn (move phase + push phase).

    The AI uses the trained MaskablePPO model via ``PushFightAgent`` to
    select moves and pushes.  The turn proceeds in two stages:

    Move phase:
      - Repeatedly asks the agent for actions until it returns a non-move
        action or makes 2 moves (the maximum per turn).
      - A safety limit of 5 attempts prevents infinite loops if the model
        keeps suggesting invalid moves.

    Push phase:
      - Tries the model's predicted push up to 5 times.
      - If all 5 attempts fail, falls back to a random valid push by syncing
        the environment state and sampling from the action mask.
      - If even random fallback fails (no legal push exists), the AI forfeits.

    Args:
        agent: A ``PushFightAgent`` instance with a loaded model.
        game_state: The current ``GameState`` instance (modified in place).
    """
    print(colorize("\n=== AI'S TURN ===", Colors.BOLD))
    print(colorize("AI is thinking...", Colors.CYAN))

    # --- Move phase: up to 2 optional moves ---
    # The agent may choose to make 0, 1, or 2 moves before pushing.
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
                # Move was rejected by the engine; stop trying to move.
                break
        else:
            # Agent returned a non-move action (push) or None; proceed to push.
            break

    if game_state.game_over:
        return

    # --- Push phase: mandatory push ---
    print(colorize("AI is pushing...", Colors.CYAN))
    # Direction names for display purposes.
    dir_names = {(-1, 0): 'up', (1, 0): 'down', (0, -1): 'left', (0, 1): 'right'}

    # Attempt the model's predicted push up to 5 times.
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

    # --- Fallback: all model attempts failed, try a random valid push ---
    # This syncs the lightweight env to the current game state and samples
    # from the full action mask, bypassing the model's prediction entirely.
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

    # --- Last resort: no legal push exists, AI loses by forfeit ---
    print(colorize("AI has no legal push available!", Colors.YELLOW))
    game_state.game_over = True
    opponent = 'white' if game_state.current_player == 'black' else 'black'
    game_state.winner = opponent


def save_game_log(game_state):
    """Save the complete game history to a JSON file for post-game analysis.

    The log includes the winner, the full move history (from the game engine's
    move_log), and a snapshot of the final board state.  Files are saved to
    the ``game_logs/`` directory with a timestamped filename.

    Args:
        game_state: The finished ``GameState`` instance with move_log populated.
    """
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
    """Run an interactive game of Push Fight: human vs trained AI.

    Loads a trained MaskablePPO model, creates a game with the standard
    initial layout, and alternates between human input and AI prediction
    until the game ends.  The game result is displayed and logged.

    Args:
        model_path: Path to the trained model file.  Supports .zip files,
            extensionless paths, and directories (resolved by PushFightAgent).
        human_team: Which color the human plays ('white' goes first,
            'black' goes second).  Default is 'white'.
        difficulty: AI difficulty label.  Not currently used for logic (the
            model determines AI strength), but kept for future compatibility.
    """
    # --- Resolve model path ---
    # Stable-Baselines3 saves models as .zip files, but users often pass
    # directory paths or paths without the extension.
    original_path = model_path

    # If it's a directory, look for a sibling .zip file with the same name.
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

    # If path doesn't end with .zip, try appending the extension.
    if not model_path.endswith('.zip'):
        zip_path = model_path + ".zip"
        if os.path.exists(zip_path):
            model_path = zip_path

    # --- Load the AI agent ---
    if not os.path.exists(model_path):
        print(colorize(f"Error: Model not found at {model_path}", Colors.RED))
        print(colorize(f"Also checked: {original_path}", Colors.YELLOW))
    try:
        print(colorize(f"Loading model from {model_path}...", Colors.CYAN))
        agent = PushFightAgent(model_path)
        print(colorize("\u2713 Model loaded!", Colors.GREEN))
    except FileNotFoundError as e:
        print(colorize(f"Error: {e}", Colors.RED))
        print(colorize("Train a model first with: python -m app.rl.train --train", Colors.YELLOW))
        return

    # --- Create the game with the standard initial layout ---
    game = GameState.create_initial_game()

    # Set human team: if black, swap the starting player so AI goes first.
    if human_team == 'black':
        game.current_player = 'black'

    # --- Display game header ---
    print(colorize("\n" + "="*60, Colors.BOLD))
    print(colorize("PLAYING AGAINST AI", Colors.BOLD))
    print(colorize("="*60, Colors.BOLD))
    print(colorize(f"You are playing as: {human_team.upper()}", Colors.BOLD))
    print(colorize("="*60 + "\n", Colors.BOLD))

    # --- Main game loop ---
    while not game.game_over:
        if game.current_player == human_team:
            # Human's turn: interactive move + push input.
            if not human_move(game):
                print(colorize("\nGame quit by user.", Colors.YELLOW))
                return
        else:
            # AI's turn: model prediction with fallback logic.
            ai_turn(agent, game)

        # Check for game-ending conditions after each turn.
        game.check_game_over()

    # --- Display game result ---
    print(colorize("\n" + "="*60, Colors.BOLD))
    if game.winner == human_team:
        print(colorize("\U0001f389 YOU WIN! \U0001f389", Colors.GREEN + Colors.BOLD))
    else:
        print(colorize("\U0001f916 AI WINS! \U0001f916", Colors.RED + Colors.BOLD))
    print(colorize("="*60, Colors.BOLD))
    save_game_log(game)
    print_board(game)


def main():
    """Entry point for the human-vs-AI CLI.

    Parses command-line arguments for model path and team selection,
    then starts an interactive game session.
    """
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
