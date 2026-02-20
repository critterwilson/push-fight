"""
Game state orchestrator for Push Fight: BJJ Edition.

This module manages the high-level game lifecycle:

  1. **Setup phase** — Players place their 5 pieces (3 square + 2 round)
     on their half of the board.  White places on rows 0–4 (north),
     black on rows 5–9 (south).

  2. **Turn flow** — Each turn consists of:
       a. Up to 2 optional *moves* (slide a piece along empty cells).
       b. Exactly 1 mandatory *push* (shove with a square piece).
     After the push, an anchor marker is placed on the pushing piece
     and play passes to the opponent.

  3. **Win conditions** — A player loses if any of the following occur:
       - 1 of their round pieces is pushed into a kill zone.
       - 2 of their square pieces are pushed into kill zones.
       - They have no legal push available at the start of their turn.

The GameState class coordinates between the Board (spatial layout) and
the Piece models, enforcing all rules and maintaining a move log.
"""

from datetime import datetime
from .board import PushFightBoard
from .pieces import Piece


class GameState:
    """Central game state tracking turn flow, win conditions, and setup phase.

    Attributes:
        board:            The PushFightBoard with piece positions.
        current_player:   'white' or 'black' — whose turn it is.
        setup_mode:       True during the initial piece-placement phase.
        moves_made:       Number of moves used this turn (0–2).
        push_completed:   True once the mandatory push has been executed.
        game_over:        True when a win condition has been met.
        winner:           'white', 'black', or None.
        pieces_pushed_off: Per-team count of eliminated pieces by shape.
        move_log:         Chronological list of all actions for replay.
    """

    def __init__(self, board: PushFightBoard | None = None, setup_mode: bool = False):
        self.board = board if board else PushFightBoard()
        self.current_player = 'white'  # White always moves first

        # Setup phase tracking
        self.setup_mode = setup_mode

        # Turn state — reset each time play passes to the other player
        self.moves_made = 0         # 0, 1, or 2 moves used this turn
        self.push_completed = False  # Becomes True after the mandatory push

        # Win state
        self.game_over = False
        self.winner = None

        # Elimination tracking — indexed by team then piece shape.
        # Win condition: 2 squares OR 1 round piece pushed off = loss.
        self.pieces_pushed_off = {
            'white': {'squares': 0, 'rounds': 0},
            'black': {'squares': 0, 'rounds': 0},
        }

        # Chronological action log for move history / replay
        self.move_log = []

    # ------------------------------------------------------------------
    # Turn-phase queries
    # ------------------------------------------------------------------

    def can_move(self) -> bool:
        """Return True if the current player has moves remaining this turn.

        A player may make 0, 1, or 2 moves before their mandatory push.
        """
        return self.moves_made < 2 and not self.push_completed

    def can_push(self) -> bool:
        """Return True if the push phase is still available.

        A push can be performed at any point during the turn (even if
        the player has not used any moves), as long as the push hasn't
        already been completed.
        """
        return not self.push_completed

    def switch_turn(self) -> None:
        """End the current turn and pass play to the opponent.

        Raises ValueError if the mandatory push has not been completed,
        since a turn cannot end without a push.
        """
        if not self.push_completed:
            raise ValueError("You must push to complete your turn!")

        self.current_player = 'black' if self.current_player == 'white' else 'white'
        self.moves_made = 0
        self.push_completed = False

    # ------------------------------------------------------------------
    # Piece counting utilities
    # ------------------------------------------------------------------

    def count_pieces(self, team: str, shape: str | None = None) -> int:
        """Count pieces on the board for a team, optionally filtered by shape.

        Args:
            team:  'white' or 'black'.
            shape: 'square', 'round', or None to count all pieces.

        Returns:
            Number of matching pieces currently on the board.
        """
        count = 0
        for y in range(10):
            for x in range(4):
                piece = self.board.get_piece(y, x)
                if piece and piece != "OUT_OF_BOUNDS" and piece.team == team:
                    if shape is None or piece.shape == shape:
                        count += 1
        return count

    def count_square_pieces(self, team: str) -> int:
        """Count square (pusher) pieces remaining on the board for *team*."""
        return self.count_pieces(team, 'square')

    def count_round_pieces(self, team: str) -> int:
        """Count round (non-pusher) pieces remaining on the board for *team*."""
        return self.count_pieces(team, 'round')

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    def perform_move(self, from_pos: tuple, to_pos: tuple) -> tuple[bool, str]:
        """Execute a move action: slide a piece from one cell to another.

        Validates that:
          - The game is in play (not setup, not over).
          - The player has moves remaining this turn.
          - The selected piece belongs to the current player.
          - The destination is reachable via BFS pathfinding.

        Returns:
            (success, message) tuple.
        """
        from_y, from_x = from_pos
        to_y, to_x = to_pos

        if self.setup_mode or self.game_over:
            return False, "Cannot move in current state"

        if not self.can_move():
            return False, "Cannot move - must push now"

        piece = self.board.get_piece(from_y, from_x)
        if not piece or piece.team != self.current_player:
            return False, "Invalid piece selection"

        valid_moves = self.board.get_valid_moves(from_y, from_x)
        if (to_y, to_x) not in valid_moves:
            return False, "Invalid move destination"

        # Execute the slide: clear origin, place at destination
        self.board.pieces[from_y][from_x] = None
        self.board.pieces[to_y][to_x] = piece
        self.moves_made += 1

        self.log_action('move', from_pos=from_pos, to_pos=to_pos)
        return True, "Piece moved"

    def log_action(self, action_type: str, **kwargs) -> None:
        """Append an action entry to the move log with a timestamp."""
        entry = {
            'type': action_type,
            'player': self.current_player,
            'timestamp': datetime.now().isoformat(),
            **kwargs,
        }
        self.move_log.append(entry)

    def perform_push(self, y: int, x: int, direction: tuple) -> bool:
        """Execute a push action with the square piece at (y, x).

        Push rules:
          - Only square pieces can initiate a push.
          - The push direction is a unit vector: (dy, dx).
          - All contiguous pieces along the push direction form a "chain"
            and are displaced one cell in that direction.
          - If the chain includes the anchored piece, the push is blocked
            (nothing moves), but the pusher still expends their push.
          - If the end of the chain lands in a kill zone, the piece is
            eliminated and a win condition may be triggered.
          - Side rails (out-of-bounds coordinates) block pushes entirely.

        Args:
            y, x:      Position of the pushing piece.
            direction: (dy, dx) unit vector for push direction.

        Returns:
            True if the push was executed (even if blocked by anchor),
            False if the push was invalid.
        """
        piece = self.board.get_piece(y, x)

        # Validation: only square pieces belonging to the current player can push
        if not piece or piece.shape != 'square':
            return False
        if piece.team != self.current_player:
            return False

        dy, dx = direction
        chain, landing_spot = self.board.get_push_chain(y, x, dy, dx)

        # Side-rail check: if the landing spot is outside the 10×4 array,
        # the push is blocked by an impassable wall
        if not self.board.is_on_board(*landing_spot):
            return False

        # Kill-zone pushes are intentionally ALLOWED — pushing pieces off
        # the board is the primary win mechanic

        # Check if the anchor piece is anywhere in the push chain.
        # If so, the entire chain is immobilized (nothing moves).
        anchor_in_chain = False
        if self.board.anchor_pos[0] is not None:
            for pos in chain:
                if pos == self.board.anchor_pos:
                    anchor_in_chain = True
                    break

        # Displace pieces in reverse order (tail-first) to avoid overwrites
        pieces_pushed_off = []  # Track eliminated pieces for win-condition check

        if not anchor_in_chain:
            for i in range(len(chain) - 1, -1, -1):
                curr_y, curr_x = chain[i]
                new_y, new_x = curr_y + dy, curr_x + dx

                moving_piece = self.board.pieces[curr_y][curr_x]
                if moving_piece is None:
                    continue

                if self.board.is_kill_zone(new_y, new_x):
                    # Piece is eliminated — remove it from the board
                    self.board.pieces[curr_y][curr_x] = None
                    pieces_pushed_off.append((moving_piece, moving_piece.team))
                else:
                    # Normal displacement — slide one cell in push direction
                    self.board.pieces[curr_y][curr_x] = None
                    self.board.pieces[new_y][new_x] = moving_piece

        self.log_action('push', piece=(y, x), direction=direction)

        # Update the anchor to the pushing piece's new position.
        # If blocked by anchor, the pusher didn't move, so anchor stays at (y, x).
        if anchor_in_chain:
            anchor_y, anchor_x = y, x
        else:
            anchor_y, anchor_x = y + dy, x + dx

        if (self.board.is_on_board(anchor_y, anchor_x)
                and not self.board.is_kill_zone(anchor_y, anchor_x)):
            self.board.anchor_pos = (anchor_y, anchor_x)
        else:
            # Anchor piece was pushed into a kill zone — clear anchor
            self.board.anchor_pos = (None, None)

        # Process eliminations and check for victory
        if pieces_pushed_off:
            for elim_piece, team in pieces_pushed_off:
                if elim_piece.shape == 'square':
                    self.pieces_pushed_off[team]['squares'] += 1
                else:
                    self.pieces_pushed_off[team]['rounds'] += 1

            if self.check_game_over():
                self.push_completed = True
                return True

        self.push_completed = True
        return True

    # ------------------------------------------------------------------
    # Win-condition evaluation
    # ------------------------------------------------------------------

    def check_game_over(self) -> bool:
        """Evaluate whether the game has ended.

        Loss conditions (per team):
          - 2 or more square pieces eliminated, OR
          - 1 or more round pieces eliminated.

        Returns:
            True if a winner has been determined.
        """
        if self.game_over:
            return True

        white_sq = self.pieces_pushed_off['white']['squares']
        white_rd = self.pieces_pushed_off['white']['rounds']
        black_sq = self.pieces_pushed_off['black']['squares']
        black_rd = self.pieces_pushed_off['black']['rounds']

        # White loses if 2 squares or 1 round piece eliminated
        if white_sq >= 2 or white_rd >= 1:
            self.game_over = True
            self.winner = 'black'
            return True

        # Black loses if 2 squares or 1 round piece eliminated
        if black_sq >= 2 or black_rd >= 1:
            self.game_over = True
            self.winner = 'white'
            return True

        return False

    def has_legal_push(self) -> bool:
        """Return True if the current player has at least one legal push.

        A player with no legal push at the start of their turn forfeits.
        Pushes are blocked only by side rails (not by the anchor).
        """
        for y in range(10):
            for x in range(4):
                piece = self.board.get_piece(y, x)
                if (piece
                        and piece.team == self.current_player
                        and piece.shape == 'square'):
                    for dy, dx in PushFightBoard.DIRECTIONS:
                        _, landing_spot = self.board.get_push_chain(y, x, dy, dx)
                        # Only side rails block — anchor no longer prevents pushes
                        if self.board.is_on_board(*landing_spot):
                            return True
        return False

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @staticmethod
    def create_initial_game() -> "GameState":
        """Create a standard game with the default piece arrangement.

        Default layout places pieces near the center line:
          White: row 4 (sleeve, lapel, belt, neck) + row 3 (joint)
          Black: row 5 (sleeve, lapel, belt, neck) + row 6 (joint)
        """
        board = PushFightBoard()

        # White team — rows 3–4 (north half, adjacent to center line)
        board.pieces[4][0] = Piece('white', 'square', name='sleeve')
        board.pieces[4][1] = Piece('white', 'square', name='lapel')
        board.pieces[4][2] = Piece('white', 'square', name='belt')
        board.pieces[4][3] = Piece('white', 'round',  name='neck')
        board.pieces[3][1] = Piece('white', 'round',  name='joint')

        # Black team — rows 5–6 (south half, adjacent to center line)
        board.pieces[5][0] = Piece('black', 'square', name='sleeve')
        board.pieces[5][1] = Piece('black', 'square', name='lapel')
        board.pieces[5][2] = Piece('black', 'square', name='belt')
        board.pieces[5][3] = Piece('black', 'round',  name='neck')
        board.pieces[6][1] = Piece('black', 'round',  name='joint')

        return GameState(board)

    @staticmethod
    def create_custom_game() -> "GameState":
        """Create an empty board in setup mode for manual piece placement."""
        board = PushFightBoard()
        return GameState(board, setup_mode=True)

    # ------------------------------------------------------------------
    # Setup-phase methods
    # ------------------------------------------------------------------

    def _is_on_player_side(self, y: int, team: str) -> bool:
        """Check if row *y* is on *team*'s half of the board.

        White occupies rows 0–4 (north); black occupies rows 5–9 (south).
        """
        if team == 'white':
            return 0 <= y <= 4
        elif team == 'black':
            return 5 <= y <= 9
        return False

    def _is_playable_space(self, y: int, x: int) -> bool:
        """Return True if (y, x) is a playable (non-kill-zone) cell."""
        if not self.board.is_on_board(y, x):
            return False
        return self.board.grid[y][x] == 0

    def get_placement_status(self, team: str) -> dict:
        """Return piece counts for *team* during setup.

        Returns:
            dict with keys 'squares', 'rounds', and 'total'.
        """
        squares = self.count_square_pieces(team)
        rounds = self.count_round_pieces(team)
        return {
            'squares': squares,
            'rounds': rounds,
            'total': squares + rounds,
        }

    def place_piece(self, y: int, x: int, team: str, shape: str,
                    name: str | None = None) -> tuple[bool, str]:
        """Place a piece during the setup phase with full validation.

        Validates:
          - Game is in setup mode.
          - Shape and team are valid strings.
          - Cell is on the player's half, playable, and unoccupied.
          - Team has not exceeded the piece limit (3 square, 2 round).

        Returns:
            (success, message) tuple.
        """
        if not self.setup_mode:
            return False, "Game is not in setup mode"

        if shape not in ['square', 'round']:
            return False, f"Invalid shape: {shape}. Must be 'square' or 'round'"

        if team not in ['white', 'black']:
            return False, f"Invalid team: {team}. Must be 'white' or 'black'"

        if not self._is_on_player_side(y, team):
            return False, f"Position ({y}, {x}) is not on {team} team's side of the centerline"

        if not self._is_playable_space(y, x):
            return False, f"Position ({y}, {x}) is not a playable space (kill zone or out of bounds)"

        if self.board.is_occupied(y, x):
            return False, f"Position ({y}, {x}) is already occupied"

        # Enforce per-shape placement limits
        status = self.get_placement_status(team)
        if shape == 'square' and status['squares'] >= 3:
            return False, f"{team} team already has 3 square pieces (maximum)"
        elif shape == 'round' and status['rounds'] >= 2:
            return False, f"{team} team already has 2 round pieces (maximum)"

        self.board.pieces[y][x] = Piece(team, shape, name=name)
        return True, f"{team} {shape} piece placed at ({y}, {x})"

    def remove_piece(self, y: int, x: int) -> tuple[bool, str]:
        """Remove a piece from the board during setup (undo a placement).

        Returns:
            (success, message) tuple.
        """
        if not self.setup_mode:
            return False, "Game is not in setup mode"

        if not self.board.is_on_board(y, x):
            return False, f"Position ({y}, {x}) is out of bounds"

        piece = self.board.get_piece(y, x)
        if piece is None:
            return False, f"No piece at position ({y}, {x})"

        self.board.pieces[y][x] = None
        return True, f"Piece removed from ({y}, {x})"

    def _validate_team_placement(self, team: str,
                                  required_squares: int = 3,
                                  required_rounds: int = 2) -> tuple[bool, str | None]:
        """Verify that *team* has exactly the required piece counts.

        Returns:
            (is_valid, error_message) — error_message is None when valid.
        """
        status = self.get_placement_status(team)
        if status['squares'] != required_squares:
            return False, (f"{team.capitalize()} team must have exactly "
                           f"{required_squares} square pieces (currently {status['squares']})")
        if status['rounds'] != required_rounds:
            return False, (f"{team.capitalize()} team must have exactly "
                           f"{required_rounds} round pieces (currently {status['rounds']})")
        return True, None

    def can_start_game(self) -> tuple[bool, str]:
        """Check whether both teams have valid placements to begin play.

        Each team needs exactly 3 square and 2 round pieces on their half.

        Returns:
            (can_start, message) tuple.
        """
        if not self.setup_mode:
            return False, "Game is not in setup mode"

        is_valid, error = self._validate_team_placement('white')
        if not is_valid:
            return False, error

        is_valid, error = self._validate_team_placement('black')
        if not is_valid:
            return False, error

        return True, "Both teams have valid piece placement"

    def start_game(self) -> tuple[bool, str]:
        """Transition from setup mode to active gameplay.

        Validates that both teams have correct piece counts before
        clearing setup mode and starting with white's turn.

        Returns:
            (success, message) tuple.
        """
        can_start, message = self.can_start_game()
        if not can_start:
            return False, message

        self.setup_mode = False
        self.current_player = 'white'
        return True, "Game started! White team goes first."

    # ------------------------------------------------------------------
    # Serialization & persistence
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the full game state to a JSON-compatible dictionary."""
        return {
            'board': self.board.to_dict(),
            'current_player': self.current_player,
            'setup_mode': self.setup_mode,
            'moves_made': self.moves_made,
            'push_completed': self.push_completed,
            'game_over': self.game_over,
            'winner': self.winner,
            'pieces_pushed_off': self.pieces_pushed_off,
        }

    @staticmethod
    def from_dict(data: dict) -> "GameState":
        """Reconstruct a GameState from a serialized dictionary."""
        board = PushFightBoard.from_dict(data['board'])
        setup_mode = data.get('setup_mode', False)
        game = GameState(board, setup_mode=setup_mode)
        game.current_player = data['current_player']
        game.moves_made = data['moves_made']
        game.push_completed = data['push_completed']
        game.game_over = data['game_over']
        game.winner = data['winner']
        game.pieces_pushed_off = data.get('pieces_pushed_off', {
            'white': {'squares': 0, 'rounds': 0},
            'black': {'squares': 0, 'rounds': 0},
        })
        return game

    def save_to_file(self, filepath: str) -> None:
        """Persist game state to a JSON file on disk."""
        import json
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load_from_file(filepath: str) -> "GameState":
        """Load a previously saved game state from a JSON file."""
        import json
        with open(filepath, 'r') as f:
            data = json.load(f)
        return GameState.from_dict(data)
