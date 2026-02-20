def format_game_state(game):
    """
    Formats the game state into a structured string context for the LLM.

    Args:
        game: The GameState object.

    Returns:
        str: A text representation of the game state including phase,
             piece positions, anchor, and recent moves.
    """
    lines = []

    # 1. Phase and turn info
    if game.game_over:
        lines.append(f"GAME OVER. Winner: {game.winner}.")
    elif game.setup_mode:
        lines.append("Phase: Setup (placing pieces).")
    elif game.push_completed:
        lines.append(f"Turn complete. Waiting for turn switch.")
    elif game.moves_made >= 2:
        lines.append(f"Current player: {game.current_player}. Phase: PUSH (must push now, 0 moves remaining).")
    else:
        remaining = 2 - game.moves_made
        lines.append(f"Current player: {game.current_player}. Phase: MOVE ({remaining} move(s) remaining, or skip to push).")

    # 2. Anchor
    ay, ax = game.board.anchor_pos
    if ay is not None:
        anchor_piece = game.board.get_piece(ay, ax)
        if anchor_piece and anchor_piece != "OUT_OF_BOUNDS":
            col_letter = chr(ord('A') + ax)
            row_num = ay + 1
            lines.append(f"Anchor: on {anchor_piece.team}'s {anchor_piece.name} at {col_letter}{row_num}. Opponent cannot move or push this piece.")
        else:
            lines.append("Anchor: placed but piece missing (pushed off).")
    else:
        lines.append("Anchor: none (first turn or cleared).")

    # 3. Piece inventory per team
    for team in ['white', 'black']:
        pieces = []
        for y in range(10):
            for x in range(4):
                p = game.board.get_piece(y, x)
                if p and p != "OUT_OF_BOUNDS" and p.team == team:
                    col_letter = chr(ord('A') + x)
                    row_num = y + 1
                    pieces.append(f"{p.name} ({p.shape}) at {col_letter}{row_num}")
        lines.append(f"{team.capitalize()} pieces: {', '.join(pieces) if pieces else 'none on board'}.")

    # 4. Eliminations
    elim_parts = []
    for team in ['white', 'black']:
        sq = game.pieces_pushed_off[team]['squares']
        rd = game.pieces_pushed_off[team]['rounds']
        if sq > 0 or rd > 0:
            elim_parts.append(f"{team}: {sq} square(s), {rd} round(s) eliminated")
    if elim_parts:
        lines.append(f"Eliminations: {'; '.join(elim_parts)}.")
    else:
        lines.append("Eliminations: none.")

    # 5. Recent moves (last 3)
    if hasattr(game, 'move_log') and game.move_log:
        recent = game.move_log[-3:]
        move_strs = []
        for entry in recent:
            if entry.get('type') == 'move':
                move_strs.append(f"{entry['player']} moved {entry.get('from_pos')}→{entry.get('to_pos')}")
            elif entry.get('type') == 'push':
                move_strs.append(f"{entry['player']} pushed from {entry.get('piece')} dir={entry.get('direction')}")
            else:
                move_strs.append(str(entry))
        lines.append(f"Recent actions: {'; '.join(move_strs)}.")

    return "\n".join(lines)
