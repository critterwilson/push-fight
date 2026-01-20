"""API routes for Push Fight game."""

from flask import jsonify, request, render_template
from app.engine.game_state import GameState
from app.storage import save_game, load_game, list_saves, delete_save


# Global game state (in production, use session management or database)
_game_state = None


def register_routes(app):
    """Register all API routes with the Flask app."""
    
    @app.route('/')
    def index():
        """API root endpoint."""
        return jsonify({
            'message': 'Push Fight API',
            'endpoints': {
                'game_state': '/api/game/state',
                'new_game': '/api/game/new',
                'move': '/api/game/move',
                'push': '/api/game/push',
                'health': '/api/health'
            }
        })
    
    @app.route('/api/game/state', methods=['GET'])
    def get_game_state():
        """Get current game state."""
        global _game_state
        if _game_state is None:
            return jsonify({'error': 'No game in progress'}), 404
        
        try:
            state_dict = _game_state.to_dict()
            # Add placement status for setup mode
            if _game_state.setup_mode:
                state_dict['placement_status'] = {
                    'white': _game_state.get_placement_status('white'),
                    'brown': _game_state.get_placement_status('brown')
                }
            return jsonify(state_dict)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/game/new', methods=['POST'])
    def new_game():
        """Create a new game."""
        global _game_state
        try:
            data = request.get_json() or {}
            custom_placement = data.get('custom_placement', False)
            
            if custom_placement:
                _game_state = GameState.create_custom_game()
            else:
                _game_state = GameState.create_initial_game()
            
            return jsonify({
                'message': 'New game created',
                'setup_mode': _game_state.setup_mode,
                'state': _game_state.to_dict()
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/game/move', methods=['POST'])
    def move_piece():
        """Move a piece."""
        global _game_state
        if _game_state is None:
            return jsonify({'error': 'No game in progress'}), 404
        
        if _game_state.setup_mode:
            return jsonify({'error': 'Game is in setup mode'}), 400
        
        if _game_state.game_over:
            return jsonify({'error': 'Game is over'}), 400
        
        try:
            data = request.get_json()
            if not data or 'from' not in data or 'to' not in data:
                return jsonify({'error': 'Missing "from" or "to" coordinates'}), 400
            
            from_pos = data['from']
            to_pos = data['to']
            
            if len(from_pos) != 2 or len(to_pos) != 2:
                return jsonify({'error': 'Invalid coordinates'}), 400
            
            from_y, from_x = from_pos
            to_y, to_x = to_pos
            
            # Validate piece belongs to current player
            piece = _game_state.board.get_piece(from_y, from_x)
            if not piece or piece.team != _game_state.current_player:
                return jsonify({'error': 'Invalid piece or not your turn'}), 400
            
            # Get valid moves
            valid_moves = _game_state.board.get_valid_moves(from_y, from_x)
            if (to_y, to_x) not in valid_moves:
                return jsonify({'error': 'Invalid move destination'}), 400
            
            # Perform move
            _game_state.board.pieces[from_y][from_x] = None
            _game_state.board.pieces[to_y][to_x] = piece
            _game_state.moves_made += 1
            
            return jsonify({
                'message': 'Piece moved',
                'state': _game_state.to_dict()
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/game/push', methods=['POST'])
    def push_piece():
        """Perform a push."""
        global _game_state
        if _game_state is None:
            return jsonify({'error': 'No game in progress'}), 404
        
        if _game_state.setup_mode:
            return jsonify({'error': 'Game is in setup mode'}), 400
        
        if _game_state.game_over:
            return jsonify({'error': 'Game is over'}), 400
        
        try:
            data = request.get_json()
            if not data or 'piece' not in data or 'direction' not in data:
                return jsonify({'error': 'Missing "piece" or "direction"'}), 400
            
            piece_pos = data['piece']
            direction = data['direction']
            
            if len(piece_pos) != 2 or len(direction) != 2:
                return jsonify({'error': 'Invalid coordinates or direction'}), 400
            
            y, x = piece_pos
            dy, dx = direction
            
            # Perform push
            success = _game_state.perform_push(y, x, (dy, dx))
            if not success:
                return jsonify({'error': 'Invalid push'}), 400
            
            # Switch turn if push was successful
            if _game_state.push_completed:
                _game_state.switch_turn()
            
            return jsonify({
                'message': 'Push successful',
                'state': _game_state.to_dict()
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/game/place', methods=['POST'])
    def place_piece():
        """Place a piece during setup."""
        global _game_state
        if _game_state is None:
            return jsonify({'error': 'No game in progress'}), 404
        
        if not _game_state.setup_mode:
            return jsonify({'error': 'Game is not in setup mode'}), 400
        
        try:
            data = request.get_json()
            if not data or 'y' not in data or 'x' not in data or 'team' not in data or 'shape' not in data:
                return jsonify({'error': 'Missing required fields: y, x, team, shape'}), 400
            
            y = data['y']
            x = data['x']
            team = data['team']
            shape = data['shape']
            
            success, message = _game_state.place_piece(y, x, team, shape)
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({
                'message': message,
                'state': _game_state.to_dict(),
                'placement_status': {
                    'white': _game_state.get_placement_status('white'),
                    'brown': _game_state.get_placement_status('brown')
                }
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/game/remove', methods=['POST'])
    def remove_piece():
        """Remove a piece during setup."""
        global _game_state
        if _game_state is None:
            return jsonify({'error': 'No game in progress'}), 404
        
        if not _game_state.setup_mode:
            return jsonify({'error': 'Game is not in setup mode'}), 400
        
        try:
            data = request.get_json()
            if not data or 'y' not in data or 'x' not in data:
                return jsonify({'error': 'Missing y or x coordinates'}), 400
            
            y = data['y']
            x = data['x']
            
            success, message = _game_state.remove_piece(y, x)
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({
                'message': message,
                'state': _game_state.to_dict(),
                'placement_status': {
                    'white': _game_state.get_placement_status('white'),
                    'brown': _game_state.get_placement_status('brown')
                }
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/game/start', methods=['POST'])
    def start_game():
        """Start the game after placement."""
        global _game_state
        if _game_state is None:
            return jsonify({'error': 'No game in progress'}), 404
        
        if not _game_state.setup_mode:
            return jsonify({'error': 'Game is not in setup mode'}), 400
        
        try:
            success, message = _game_state.start_game()
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({
                'message': message,
                'state': _game_state.to_dict()
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/game/valid-moves', methods=['GET'])
    def get_valid_moves():
        """Get valid moves for a piece."""
        global _game_state
        if _game_state is None:
            return jsonify({'error': 'No game in progress'}), 404
        
        if _game_state.setup_mode:
            return jsonify({'error': 'Game is in setup mode'}), 400
        
        try:
            y = request.args.get('y', type=int)
            x = request.args.get('x', type=int)
            
            if y is None or x is None:
                return jsonify({'error': 'Missing y or x parameter'}), 400
            
            valid_moves = _game_state.board.get_valid_moves(y, x)
            # Convert set of tuples to list of lists for JSON serialization
            valid_moves_list = [[pos[0], pos[1]] for pos in valid_moves]
            
            return jsonify({
                'valid_moves': valid_moves_list
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/game/save', methods=['POST'])
    def save_game_endpoint():
        """Save the current game."""
        global _game_state
        if _game_state is None:
            return jsonify({'error': 'No game in progress'}), 404
        
        try:
            data = request.get_json() or {}
            filename = data.get('filename', 'game')
            
            if not filename:
                return jsonify({'error': 'Filename is required'}), 400
            
            save_path = save_game(_game_state, filename)
            
            return jsonify({
                'message': 'Game saved',
                'filename': filename,
                'path': save_path
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/game/saves', methods=['GET'])
    def list_saves_endpoint():
        """List all saved games."""
        try:
            saves = list_saves()
            return jsonify({
                'saves': saves
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/game/load', methods=['POST'])
    def load_game_endpoint():
        """Load a saved game."""
        global _game_state
        try:
            data = request.get_json() or {}
            filename = data.get('filename')
            
            if not filename:
                return jsonify({'error': 'Filename is required'}), 400
            
            _game_state = load_game(filename)
            
            return jsonify({
                'message': 'Game loaded',
                'filename': filename,
                'state': _game_state.to_dict()
            })
        except FileNotFoundError as e:
            return jsonify({'error': str(e)}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        return jsonify({'status': 'ok'})
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
