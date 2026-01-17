import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GameBoardComponent } from './game-board.component';
import { GameService } from '../../services/game.service';
import { of, BehaviorSubject } from 'rxjs';

describe('GameBoardComponent', () => {
  let component: GameBoardComponent;
  let fixture: ComponentFixture<GameBoardComponent>;
  let gameService: jasmine.SpyObj<GameService>;

  const mockGameState = {
    board: {
      grid: [
        [-1, -1, -1, -1],
        [-1, 0, 0, -1],
        [0, 0, 0, -1],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [-1, 0, 0, 0],
        [-1, 0, 0, -1],
        [-1, -1, -1, -1]
      ],
      pieces: Array(10).fill(null).map(() => Array(4).fill(null)),
      anchor_pos: [null, null] as [number | null, number | null]
    },
    current_player: 'white',
    setup_mode: false,
    moves_made: 0,
    push_completed: false,
    game_over: false,
    winner: null
  };

  beforeEach(async () => {
    const gameServiceSpy = jasmine.createSpyObj('GameService', [
      'getCurrentState',
      'selectPiece',
      'clearSelection',
      'movePiece',
      'placePiece',
      'removePiece',
      'getValidMoves'
    ], {
      gameState: new BehaviorSubject(mockGameState),
      selectedPiece: new BehaviorSubject<[number, number] | null>(null),
      validMoves: new BehaviorSubject<[number, number][]>([])
    });

    await TestBed.configureTestingModule({
      imports: [GameBoardComponent],
      providers: [
        { provide: GameService, useValue: gameServiceSpy }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(GameBoardComponent);
    component = fixture.componentInstance;
    gameService = TestBed.inject(GameService) as jasmine.SpyObj<GameService>;
    gameService.getCurrentState.and.returnValue(mockGameState);
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize board cells', () => {
    fixture.detectChanges();
    expect(component.boardCells.length).toBe(10);
    expect(component.boardCells[0].length).toBe(4);
  });

  it('should update board when game state changes', () => {
    fixture.detectChanges();
    const initialCells = component.boardCells.length;

    (gameService.gameState as BehaviorSubject<any>).next(mockGameState);
    fixture.detectChanges();

    expect(component.boardCells.length).toBe(10);
  });

  it('should handle cell click in setup mode', () => {
    mockGameState.setup_mode = true;
    gameService.getCurrentState.and.returnValue(mockGameState);
    (window as any).setupPanelRef = {
      removeMode: false,
      selectedTeam: 'white',
      selectedShape: 'square'
    };

    component.onCellClick(4, 0);
    expect(gameService.placePiece).toHaveBeenCalledWith(4, 0, 'white', 'square');
  });

  it('should handle cell click in remove mode', () => {
    mockGameState.setup_mode = true;
    gameService.getCurrentState.and.returnValue(mockGameState);
    (window as any).setupPanelRef = {
      removeMode: true,
      selectedTeam: 'white',
      selectedShape: 'square'
    };

    component.onCellClick(4, 0);
    expect(gameService.removePiece).toHaveBeenCalledWith(4, 0);
  });

  it('should select piece when clicking on own piece in game mode', () => {
    mockGameState.setup_mode = false;
    mockGameState.board.pieces[4][0] = { team: 'white', shape: 'square' };
    gameService.getCurrentState.and.returnValue(mockGameState);

    component.onCellClick(4, 0);
    expect(gameService.selectPiece).toHaveBeenCalledWith(4, 0, 'move');
  });

  it('should clear selection when clicking same cell', () => {
    (gameService.selectedPiece as BehaviorSubject<any>).next([4, 0]);
    mockGameState.setup_mode = false;
    gameService.getCurrentState.and.returnValue(mockGameState);

    component.onCellClick(4, 0);
    expect(gameService.clearSelection).toHaveBeenCalled();
  });

  it('should check if cell is selected', () => {
    (gameService.selectedPiece as BehaviorSubject<any>).next([4, 0]);
    expect(component.isSelected(4, 0)).toBe(true);
    expect(component.isSelected(4, 1)).toBe(false);
  });

  it('should check if cell is valid move', () => {
    (gameService.validMoves as BehaviorSubject<any>).next([[4, 1], [5, 0]]);
    expect(component.isValidMove(4, 1)).toBe(true);
    expect(component.isValidMove(4, 2)).toBe(false);
  });

  it('should check if piece is anchored', () => {
    mockGameState.board.anchor_pos = [4, 0];
    gameService.getCurrentState.and.returnValue(mockGameState);
    expect(component.isAnchored(4, 0)).toBe(true);
    expect(component.isAnchored(4, 1)).toBe(false);
  });

  it('should get piece classes', () => {
    const piece = { team: 'white', shape: 'square' };
    expect(component.getPieceClasses(piece)).toBe('white square');
  });
});
