"""
Serialise a live :class:`~app.engine.game_state.GameState` into a structured
plain-text summary suitable for inclusion in an LLM prompt.

The output covers:
  1. Current phase and turn information
  2. Anchor position (if any)
  3. Piece inventory per team (name, shape, board coordinates)
  4. Elimination counts (squares and rounds pushed off)
  5. Last 3 actions from the move log
  6. Available actions (phase-dependent: placement status, valid moves,
     or valid push directions)

Coordinates are printed in human-friendly **letter-column + 1-indexed row**
format (e.g. ``A1``, ``D10``).
"""

# The canonical five-piece roster, matching the serializer.
_PIECE_ROSTER = ['sleeve', 'lapel', 'belt', 'neck', 'joint']

_DIRECTION_NAMES = {(-1, 0): "up", (1, 0): "down", (0, -1): "left", (0, 1): "right"}


def _coord(x, y):
    """Convert column index *x* and row index *y* to a board coordinate like ``B5``."""
    return f"{chr(ord('A') + x)}{y + 1}"


def format_game_state(game):
    """
    Formats the game state into a structured string context for the LLM.

    Args:
        game: The GameState object.

    Returns:
        str: A text representation of the game state including phase,
             piece positions, anchor, recent moves, and available actions.
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

    # 1b. Setup-phase placement status
    if game.setup_mode:
        for team in ['white', 'black']:
            status = game.get_placement_status(team)
            remaining_sq = 3 - status['squares']
            remaining_rd = 2 - status['rounds']
            if remaining_sq > 0 or remaining_rd > 0:
                placed = {p.name for row in game.board.pieces for p in row if p and p.team == team}
                unplaced = [n for n in _PIECE_ROSTER if n not in placed]
                lines.append(
                    f"{team.capitalize()} needs to place: "
                    f"{remaining_sq} square, {remaining_rd} round "
                    f"({', '.join(unplaced)})."
                )
            else:
                lines.append(f"{team.capitalize()} placement complete (5/5).")

    # 2. Anchor
    ay, ax = game.board.anchor_pos
    if ay is not None:
        anchor_piece = game.board.get_piece(ay, ax)
        if anchor_piece and anchor_piece != "OUT_OF_BOUNDS":
            lines.append(f"Anchor: on {anchor_piece.team}'s {anchor_piece.name} at {_coord(ax, ay)}. Opponent cannot move or push this piece.")
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
                    pieces.append(f"{p.name} ({p.shape}) at {_coord(x, y)}")
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
                move_strs.append(f"{entry['player']} moved {entry.get('from_pos')}\u2192{entry.get('to_pos')}")
            elif entry.get('type') == 'push':
                move_strs.append(f"{entry['player']} pushed from {entry.get('piece')} dir={entry.get('direction')}")
            else:
                move_strs.append(str(entry))
        lines.append(f"Recent actions: {'; '.join(move_strs)}.")

    # 6. Available actions (phase-dependent)
    if game.setup_mode:
        pass  # Placement status already shown in section 1b
    elif game.game_over:
        lines.append("No actions available (game is over).")
    elif game.push_completed:
        pass  # Turn is over, waiting for switch
    elif game.moves_made < 2 and not game.push_completed:
        # MOVE phase: show valid moves for each of the current player's pieces
        move_actions = []
        for y in range(10):
            for x in range(4):
                p = game.board.get_piece(y, x)
                if p and p != "OUT_OF_BOUNDS" and p.team == game.current_player:
                    # Skip anchored piece — cannot be moved
                    if (ay is not None and (y, x) == (ay, ax)):
                        move_actions.append(f"{p.name} at {_coord(x, y)}: anchored (cannot move)")
                        continue
                    destinations = game.board.get_valid_moves(y, x)
                    if destinations:
                        dest_strs = sorted(_coord(dx, dy) for dy, dx in destinations)
                        move_actions.append(
                            f"{p.name} at {_coord(x, y)}: can move to {', '.join(dest_strs)}"
                        )
                    else:
                        move_actions.append(f"{p.name} at {_coord(x, y)}: blocked (no valid moves)")
        if move_actions:
            lines.append("Valid moves:")
            lines.extend(f"  {a}" for a in move_actions)
        lines.append("You may also skip remaining moves and push now.")
    else:
        # PUSH phase: show valid push directions for current player's square pieces
        push_actions = []
        for y in range(10):
            for x in range(4):
                p = game.board.get_piece(y, x)
                if (p and p != "OUT_OF_BOUNDS"
                        and p.team == game.current_player
                        and p.shape == 'square'):
                    valid_dirs = []
                    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        chain, landing = game.board.get_push_chain(y, x, dy, dx)
                        # A push is valid when: there is an adjacent piece to push
                        # (chain > 1) and the landing spot is on the board (not a
                        # side rail).
                        if len(chain) > 1 and game.board.is_on_board(*landing):
                            valid_dirs.append(_DIRECTION_NAMES[(dy, dx)])
                    if valid_dirs:
                        push_actions.append(
                            f"{p.name} at {_coord(x, y)}: can push {', '.join(valid_dirs)}"
                        )
        if push_actions:
            lines.append("Valid pushes (must push now):")
            lines.extend(f"  {a}" for a in push_actions)
        else:
            lines.append("WARNING: No legal pushes available!")

    return "\n".join(lines)
