import os
import sys

# Ensure we can import from app
sys.path.append(os.getcwd())

from app.engine.game_state import GameState
from app.rag.rag_engine import PushFightRAG
from app.rag.state_formatter import format_game_state

def main():
    print("=== Push Fight AI Referee Demo ===")
    
    # 1. Initialize Game
    print("\n[1] Initializing Game State...")
    try:
        game = GameState.create_initial_game()
        print("    Success.")
    except Exception as e:
        print(f"    Error: {e}")
        return

    # 2. Initialize AI
    print("\n[2] Initializing RAG Engine (Ollama + ChromaDB)...")
    try:
        # Note: Ensure assets/rules.md exists
        rag = PushFightRAG(rules_path="assets/rules.md")
        print("    Success.")
    except Exception as e:
        print(f"    Error: {e}")
        return

    # 3. Simulate Gameplay
    print("\n[3] Simulating Moves...")
    # Move White piece from (4,0) to (3,0)
    game.perform_move((4, 0), (3, 0))
    print("    Moved White from (4,0) to (3,0).")

    # 4. Generate Context
    context = format_game_state(game)
    
    # 5. Ask the AI
    questions = [
        "Can I push the piece at (4, 1) to the left?",
        "Why is moving diagonally illegal?",
        "How do I win from here?"
    ]
    
    print(f"\n[5] AI Referee answering {len(questions)} questions...")
    for i, q in enumerate(questions, 1):
        print(f"\n--- Question {i}: \"{q}\" ---")
        response = rag.ask(q, context)
        print(f"AI Response: {response}")

if __name__ == "__main__":
    main()