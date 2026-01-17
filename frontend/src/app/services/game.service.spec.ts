import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { GameService, GameState, Piece } from './game.service';

describe('GameService', () => {
  let service: GameService;
  let httpMock: HttpTestingController;

  const mockGameState: GameState = {
    board: {
      grid: Array(10).fill(null).map(() => Array(4).fill(0)),
      pieces: Array(10).fill(null).map(() => Array(4).fill(null)),
      anchor_pos: [null, null]
    },
    current_player: 'white',
    setup_mode: false,
    moves_made: 0,
    push_completed: false,
    game_over: false,
    winner: null
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        GameService,
        provideHttpClient(),
        provideHttpClientTesting()
      ]
    });
    service = TestBed.inject(GameService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  describe('loadGameState', () => {
    it('should load game state from API', () => {
      service.loadGameState();

      const req = httpMock.expectOne('/api/game/state');
      expect(req.request.method).toBe('GET');
      req.flush(mockGameState);

      service.gameState.subscribe(state => {
        expect(state).toEqual(mockGameState);
      });
    });

    it('should handle error when loading game state', () => {
      service.loadGameState();

      const req = httpMock.expectOne('/api/game/state');
      req.error(new ErrorEvent('Network error'));

      service.gameState.subscribe(state => {
        expect(state).toBeNull();
      });
    });
  });

  describe('newGame', () => {
    it('should create a new standard game', () => {
      service.newGame(false).subscribe();

      const req = httpMock.expectOne('/api/game/new');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ custom_placement: false });
      req.flush({ message: 'Game created', state: mockGameState });
    });

    it('should create a new custom game', () => {
      service.newGame(true).subscribe();

      const req = httpMock.expectOne('/api/game/new');
      expect(req.request.body).toEqual({ custom_placement: true });
      req.flush({ message: 'Custom game created', state: mockGameState });
    });
  });

  describe('movePiece', () => {
    it('should move a piece', () => {
      service.movePiece([4, 0], [3, 0]).subscribe();

      const req = httpMock.expectOne('/api/game/move');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ from: [4, 0], to: [3, 0] });
      req.flush({ message: 'Piece moved' });
    });
  });

  describe('pushPiece', () => {
    it('should push a piece', () => {
      service.pushPiece([4, 0], [1, 0]).subscribe();

      const req = httpMock.expectOne('/api/game/push');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ piece: [4, 0], direction: [1, 0] });
      req.flush({ message: 'Push successful' });
    });
  });

  describe('placePiece', () => {
    it('should place a piece during setup', () => {
      service.placePiece(4, 0, 'white', 'square').subscribe();

      const req = httpMock.expectOne('/api/game/place');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ y: 4, x: 0, team: 'white', shape: 'square' });
      req.flush({ message: 'Piece placed' });
    });
  });

  describe('removePiece', () => {
    it('should remove a piece during setup', () => {
      service.removePiece(4, 0).subscribe();

      const req = httpMock.expectOne('/api/game/remove');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ y: 4, x: 0 });
      req.flush({ message: 'Piece removed' });
    });
  });

  describe('startGame', () => {
    it('should start the game', () => {
      service.startGame().subscribe();

      const req = httpMock.expectOne('/api/game/start');
      expect(req.request.method).toBe('POST');
      req.flush({ message: 'Game started' });
    });
  });

  describe('getValidMoves', () => {
    it('should get valid moves for a piece', () => {
      const mockMoves: [number, number][] = [[3, 0], [4, 1], [5, 0]];

      service.getValidMoves(4, 0).subscribe(moves => {
        expect(moves).toEqual(mockMoves);
      });

      const req = httpMock.expectOne('/api/game/valid-moves?y=4&x=0');
      expect(req.request.method).toBe('GET');
      req.flush({ valid_moves: mockMoves });
    });
  });

  describe('saveGame', () => {
    it('should save the game', () => {
      service.saveGame('test_game').subscribe();

      const req = httpMock.expectOne('/api/game/save');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ filename: 'test_game' });
      req.flush({ message: 'Game saved' });
    });
  });

  describe('listSaves', () => {
    it('should list saved games', () => {
      const mockSaves = ['game1', 'game2', 'game3'];

      service.listSaves().subscribe(saves => {
        expect(saves).toEqual(mockSaves);
      });

      const req = httpMock.expectOne('/api/game/saves');
      expect(req.request.method).toBe('GET');
      req.flush({ saves: mockSaves });
    });
  });

  describe('loadGame', () => {
    it('should load a saved game', () => {
      service.loadGame('test_game').subscribe();

      const req = httpMock.expectOne('/api/game/load');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ filename: 'test_game' });
      req.flush({ message: 'Game loaded', state: mockGameState });
    });
  });

  describe('selection management', () => {
    it('should select a piece', () => {
      service.selectPiece(4, 0, 'move');

      service.selectedPiece.subscribe(pos => {
        expect(pos).toEqual([4, 0]);
      });

      service.actionMode.subscribe(mode => {
        expect(mode).toBe('move');
      });
    });

    it('should clear selection', () => {
      service.selectPiece(4, 0, 'move');
      service.clearSelection();

      service.selectedPiece.subscribe(pos => {
        expect(pos).toBeNull();
      });

      service.actionMode.subscribe(mode => {
        expect(mode).toBeNull();
      });
    });
  });

  describe('getCurrentState', () => {
    it('should return current game state', () => {
      service.loadGameState();
      const req = httpMock.expectOne('/api/game/state');
      req.flush(mockGameState);

      const state = service.getCurrentState();
      expect(state).toEqual(mockGameState);
    });
  });
});
