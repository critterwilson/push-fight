import time
import sys
import os

# Ensure we can import from app
sys.path.append(os.getcwd())

from app.engine.game_state import GameState
from app.rag.ai_interface import AIInterface

def mock_ui_callback(response):
    """This function simulates the UI updating a text box with the answer."""
    print(f"\n\n[UI UPDATE] AI Answer Received:\n{response}\n")

def main():
    print("=== UI Integration Demo ===")
    
    # 1. Init Interface (starts loading in background)
    ai = AIInterface()
    print("UI: AI Interface initialized. Loading in background...")
    
    # 2. Simulate Game Loop / User doing other things
    game = GameState.create_initial_game()
    print("UI: Game started.")
    
    # Simulate waiting for user input or game loading
    for i in range(3):
        print(f"UI: Rendering frame {i} (Game is responsive)...")
        time.sleep(0.5)
        
    # 3. User asks a question
    question = "What happens if I push the piece at (4, 1)?"
    print(f"\nUI: User asks: '{question}'")
    
    # 4. Call Async Method
    ai.ask_question(game, question, mock_ui_callback)
    
    print("UI: Question submitted. Continuing to render frames...")
    
    # 5. Simulate Game Loop continuing while AI thinks
    for i in range(10):
        print(f"UI: Rendering frame {i+10} (Game still responsive)...")
        time.sleep(1)

if __name__ == "__main__":
    main()