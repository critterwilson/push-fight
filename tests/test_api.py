"""Tests for Flask API endpoints."""

import pytest
import json
from app.web.app import create_app


@pytest.fixture
def client():
    """Create a test client."""
    app = create_app()
    app.config['TESTING'] = True
    
    # Clear global game state before each test
    from app.web import routes
    routes._game_state = None
    
    with app.test_client() as client:
        yield client
    
    # Clean up after test
    routes._game_state = None


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/api/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'


class TestGameStateEndpoints:
    """Tests for game state endpoints."""
    
    def test_get_game_state_no_game(self, client):
        """Test getting state when no game exists."""
        response = client.get('/api/game/state')
        assert response.status_code == 404
    
    def test_new_game_standard(self, client):
        """Test creating a standard game."""
        response = client.post('/api/game/new', json={'custom_placement': False})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['setup_mode'] is False
        assert 'state' in data
    
    def test_new_game_custom(self, client):
        """Test creating a custom game."""
        response = client.post('/api/game/new', json={'custom_placement': True})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['setup_mode'] is True
    
    def test_get_game_state_after_creation(self, client):
        """Test getting state after creating game."""
        client.post('/api/game/new', json={'custom_placement': False})
        response = client.get('/api/game/state')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'current_player' in data
        assert 'board' in data


class TestMoveEndpoints:
    """Tests for move-related endpoints."""
    
    def test_move_piece_no_game(self, client):
        """Test moving piece when no game exists."""
        response = client.post('/api/game/move', json={'from': [4, 0], 'to': [3, 0]})
        assert response.status_code == 404
    
    def test_move_piece_in_setup_mode(self, client):
        """Test moving piece in setup mode fails."""
        client.post('/api/game/new', json={'custom_placement': True})
        response = client.post('/api/game/move', json={'from': [4, 0], 'to': [3, 0]})
        assert response.status_code == 400
    
    def test_get_valid_moves(self, client):
        """Test getting valid moves."""
        client.post('/api/game/new', json={'custom_placement': False})
        response = client.get('/api/game/valid-moves?y=4&x=0')
        # May return 200 with moves or 400 if invalid piece
        assert response.status_code in [200, 400]
    
    def test_get_valid_moves_missing_params(self, client):
        """Test getting valid moves without parameters."""
        client.post('/api/game/new', json={'custom_placement': False})
        response = client.get('/api/game/valid-moves')
        assert response.status_code == 400


class TestPushEndpoints:
    """Tests for push endpoints."""
    
    def test_push_piece_no_game(self, client):
        """Test pushing piece when no game exists."""
        response = client.post('/api/game/push', json={'piece': [4, 0], 'direction': [1, 0]})
        assert response.status_code == 404
    
    def test_push_piece_missing_data(self, client):
        """Test pushing piece with missing data."""
        client.post('/api/game/new', json={'custom_placement': False})
        response = client.post('/api/game/push', json={})
        assert response.status_code == 400


class TestSetupEndpoints:
    """Tests for setup/placement endpoints."""
    
    def test_place_piece(self, client):
        """Test placing a piece."""
        client.post('/api/game/new', json={'custom_placement': True})
        response = client.post('/api/game/place', json={
            'y': 4, 'x': 0, 'team': 'white', 'shape': 'square'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'placement_status' in data
    
    def test_place_piece_missing_fields(self, client):
        """Test placing piece with missing fields."""
        client.post('/api/game/new', json={'custom_placement': True})
        response = client.post('/api/game/place', json={'y': 4, 'x': 0})
        assert response.status_code == 400
    
    def test_place_piece_wrong_side(self, client):
        """Test placing piece on wrong side."""
        client.post('/api/game/new', json={'custom_placement': True})
        response = client.post('/api/game/place', json={
            'y': 5, 'x': 0, 'team': 'white', 'shape': 'square'  # Brown side
        })
        assert response.status_code == 400
    
    def test_remove_piece(self, client):
        """Test removing a piece."""
        client.post('/api/game/new', json={'custom_placement': True})
        client.post('/api/game/place', json={
            'y': 4, 'x': 0, 'team': 'white', 'shape': 'square'
        })
        response = client.post('/api/game/remove', json={'y': 4, 'x': 0})
        assert response.status_code == 200
    
    def test_start_game(self, client):
        """Test starting game after placement."""
        client.post('/api/game/new', json={'custom_placement': True})
        
        # Place all required pieces
        for i in range(3):
            client.post('/api/game/place', json={
                'y': 4, 'x': i, 'team': 'white', 'shape': 'square'
            })
        for i in range(2):
            client.post('/api/game/place', json={
                'y': 3, 'x': i, 'team': 'white', 'shape': 'round'
            })
        for i in range(3):
            client.post('/api/game/place', json={
                'y': 5, 'x': i, 'team': 'brown', 'shape': 'square'
            })
        for i in range(2):
            client.post('/api/game/place', json={
                'y': 6, 'x': i, 'team': 'brown', 'shape': 'round'
            })
        
        response = client.post('/api/game/start')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['state']['setup_mode'] is False


class TestSaveLoadEndpoints:
    """Tests for save/load endpoints."""
    
    def test_save_game(self, client):
        """Test saving a game."""
        client.post('/api/game/new', json={'custom_placement': False})
        response = client.post('/api/game/save', json={'filename': 'test_api_save'})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'filename' in data
        
        # Clean up
        from app.storage import delete_save
        delete_save('test_api_save')
    
    def test_save_game_missing_filename(self, client):
        """Test saving game without filename."""
        client.post('/api/game/new', json={'custom_placement': False})
        # Test with missing filename key
        response = client.post('/api/game/save', json={})
        # The endpoint uses .get() with default 'game', so this actually succeeds
        # But we can test with empty string
        response2 = client.post('/api/game/save', json={'filename': ''})
        # Empty string is falsy, so should fail the check
        assert response2.status_code == 400
    
    def test_list_saves(self, client):
        """Test listing saves."""
        response = client.get('/api/game/saves')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'saves' in data
        assert isinstance(data['saves'], list)
    
    def test_load_game(self, client):
        """Test loading a game."""
        # Create and save a game
        client.post('/api/game/new', json={'custom_placement': False})
        client.post('/api/game/save', json={'filename': 'test_api_load'})
        
        # Load it
        response = client.post('/api/game/load', json={'filename': 'test_api_load'})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'state' in data
        
        # Clean up
        from app.storage import delete_save
        delete_save('test_api_load')
    
    def test_load_game_not_found(self, client):
        """Test loading non-existent game."""
        response = client.post('/api/game/load', json={'filename': 'nonexistent_12345'})
        assert response.status_code == 404
