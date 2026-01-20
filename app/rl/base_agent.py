"""Base agent class with common utilities."""

from abc import ABC
from app.engine.game_state import GameState
from app.rl.agent_interface import SimpleAgent


class BaseAgent(SimpleAgent, ABC):
    """
    Base agent class with common utilities for game state analysis.
    
    Subclasses should implement get_action() and get_observation().
    """
    
    def get_valid_moves(self, game_state: GameState):
        """
        Get all valid moves for the current player.
        
        Returns:
            list: List of move dictionaries with 'from' and 'to' keys
        """
        valid_moves = []
        
        if not game_state.can_move():
            return valid_moves
        
        for y in range(10):
            for x in range(4):
                piece = game_state.board.get_piece(y, x)
                if (piece and piece != "OUT_OF_BOUNDS" and 
                    piece.team == game_state.current_player):
                    destinations = game_state.board.get_valid_moves(y, x)
                    for dest_y, dest_x in destinations:
                        valid_moves.append({
                            'from': (y, x),
                            'to': (dest_y, dest_x)
                        })
        
        return valid_moves
    
    def get_valid_pushes(self, game_state: GameState):
        """
        Get all valid pushes for the current player.
        
        Returns:
            list: List of push dictionaries with 'piece' and 'direction' keys
        """
        valid_pushes = []
        
        if not game_state.can_push():
            return valid_pushes
        
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # Up, Down, Left, Right
        
        for y in range(10):
            for x in range(4):
                piece = game_state.board.get_piece(y, x)
                if (piece and piece != "OUT_OF_BOUNDS" and 
                    piece.team == game_state.current_player and
                    piece.shape == 'square'):
                    
                    for direction in directions:
                        # Check if push is valid
                        chain, landing_spot = game_state.board.get_push_chain(y, x, *direction)
                        
                        # Check anchor
                        anchor_blocks = False
                        if game_state.board.anchor_pos[0] is not None:
                            for pos in chain:
                                if pos == game_state.board.anchor_pos:
                                    anchor_blocks = True
                                    break
                        
                        # Check side rail
                        side_rail_blocks = not game_state.board.is_on_board(*landing_spot)
                        
                        if not anchor_blocks and not side_rail_blocks:
                            valid_pushes.append({
                                'piece': (y, x),
                                'direction': direction
                            })
        
        return valid_pushes
    
    def evaluate_position(self, game_state: GameState, player: str = None):
        """
        Simple position evaluation heuristic.
        
        Args:
            game_state: Current GameState
            player: Player to evaluate for (None = current player)
            
        Returns:
            float: Evaluation score (positive = good for player)
        """
        if player is None:
            player = game_state.current_player
        
        score = 0.0
        
        # Count pieces
        my_pieces = 0
        opp_pieces = 0
        
        for y in range(10):
            for x in range(4):
                piece = game_state.board.get_piece(y, x)
                if piece and piece != "OUT_OF_BOUNDS":
                    if piece.team == player:
                        my_pieces += 1
                        # Bonus for square pieces (can push)
                        if piece.shape == 'square':
                            score += 0.5
                    else:
                        opp_pieces += 1
        
        score += (my_pieces - opp_pieces) * 2.0
        
        # Check for win/loss
        if game_state.game_over:
            if game_state.winner == player:
                score += 100.0
            else:
                score -= 100.0
        
        return score
    
    def get_observation(self, game_state: GameState):
        """
        Default observation: return game state dictionary.
        
        Subclasses can override for custom observation formats.
        """
        return game_state.to_dict()
