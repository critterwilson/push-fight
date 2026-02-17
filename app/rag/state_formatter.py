def format_game_state(game):
    """
    Formats the game state into a string context for the LLM.
    
    Args:
        game: The GameState object.
        
    Returns:
        str: A text representation of the game state including player info,
             recent moves, and the board layout.
    """
    info = []
    
    # 1. Basic Game Info
    info.append(f"Current Player: {game.current_player}")
    
    # 2. Move History (Context for what just happened)
    if hasattr(game, 'move_log'):
        info.append(f"\nRecent Moves ({len(game.move_log)} total):")
        # Show last 3 moves
        for entry in game.move_log[-3:]:
            info.append(f"  - {entry}")
            
    # 3. Board Representation
    # We rely on the board's string representation to give the LLM a visual grid.
    if hasattr(game, 'board'):
        info.append(f"\nBoard Configuration:\n{str(game.board)}")
        
    return "\n".join(info)