import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SetupPanelComponent } from './setup-panel.component';
import { GameService } from '../../services/game.service';
import { of, BehaviorSubject } from 'rxjs';

describe('SetupPanelComponent', () => {
  let component: SetupPanelComponent;
  let fixture: ComponentFixture<SetupPanelComponent>;
  let gameService: jasmine.SpyObj<GameService>;

  const mockGameState = {
    setup_mode: true,
    placement_status: {
      white: { squares: 3, rounds: 2, total: 5 },
      brown: { squares: 3, rounds: 2, total: 5 }
    }
  };

  beforeEach(async () => {
    const gameServiceSpy = jasmine.createSpyObj('GameService', [
      'getCurrentState',
      'startGame',
      'placePiece',
      'removePiece'
    ], {
      setupMode$: new BehaviorSubject(true),
      gameState: new BehaviorSubject(mockGameState)
    });

    await TestBed.configureTestingModule({
      imports: [SetupPanelComponent],
      providers: [
        { provide: GameService, useValue: gameServiceSpy }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(SetupPanelComponent);
    component = fixture.componentInstance;
    gameService = TestBed.inject(GameService) as jasmine.SpyObj<GameService>;
    gameService.getCurrentState.and.returnValue(mockGameState);
    gameService.startGame.and.returnValue(of({ message: 'Game started' }));
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should expose setupPanelRef to window', () => {
    expect((window as any).setupPanelRef).toBe(component);
  });

  it('should allow starting game when placement is complete', () => {
    expect(component.canStart()).toBe(true);
  });

  it('should not allow starting game when placement is incomplete', () => {
    gameService.getCurrentState.and.returnValue({
      ...mockGameState,
      placement_status: {
        white: { squares: 2, rounds: 2, total: 4 },
        brown: { squares: 3, rounds: 2, total: 5 }
      }
    });
    expect(component.canStart()).toBe(false);
  });

  it('should start game when startGame is called', () => {
    component.startGame();
    expect(gameService.startGame).toHaveBeenCalled();
  });

  it('should display message after starting game', (done) => {
    component.startGame();
    setTimeout(() => {
      expect(component.message).toContain('Game started');
      done();
    }, 100);
  });
});
