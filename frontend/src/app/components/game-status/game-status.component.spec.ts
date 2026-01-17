import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GameStatusComponent } from './game-status.component';
import { GameService } from '../../services/game.service';
import { BehaviorSubject } from 'rxjs';

describe('GameStatusComponent', () => {
  let component: GameStatusComponent;
  let fixture: ComponentFixture<GameStatusComponent>;
  let gameService: jasmine.SpyObj<GameService>;

  const mockGameState = {
    current_player: 'white',
    setup_mode: false,
    moves_made: 1,
    push_completed: false,
    game_over: false,
    winner: null
  };

  beforeEach(async () => {
    const gameServiceSpy = jasmine.createSpyObj('GameService', [], {
      gameState: new BehaviorSubject(mockGameState)
    });

    await TestBed.configureTestingModule({
      imports: [GameStatusComponent],
      providers: [
        { provide: GameService, useValue: gameServiceSpy }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(GameStatusComponent);
    component = fixture.componentInstance;
    gameService = TestBed.inject(GameService) as jasmine.SpyObj<GameService>;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should display current player', () => {
    fixture.detectChanges();
    const compiled = fixture.nativeElement;
    expect(compiled.textContent).toContain('white');
  });

  it('should display moves made when not in setup mode', () => {
    fixture.detectChanges();
    const compiled = fixture.nativeElement;
    expect(compiled.textContent).toContain('1/2');
  });

  it('should display setup phase when in setup mode', () => {
    (gameService.gameState as BehaviorSubject<any>).next({
      ...mockGameState,
      setup_mode: true
    });
    fixture.detectChanges();
    const compiled = fixture.nativeElement;
    expect(compiled.textContent).toContain('Setup');
  });
});
