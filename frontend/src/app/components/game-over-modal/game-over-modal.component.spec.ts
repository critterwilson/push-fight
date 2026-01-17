import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GameOverModalComponent } from './game-over-modal.component';
import { GameService } from '../../services/game.service';
import { BehaviorSubject } from 'rxjs';

describe('GameOverModalComponent', () => {
  let component: GameOverModalComponent;
  let fixture: ComponentFixture<GameOverModalComponent>;
  let gameService: jasmine.SpyObj<GameService>;

  beforeEach(async () => {
    const gameServiceSpy = jasmine.createSpyObj('GameService', [], {
      gameState: new BehaviorSubject({
        game_over: false,
        winner: null
      })
    });

    await TestBed.configureTestingModule({
      imports: [GameOverModalComponent],
      providers: [
        { provide: GameService, useValue: gameServiceSpy }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(GameOverModalComponent);
    component = fixture.componentInstance;
    gameService = TestBed.inject(GameService) as jasmine.SpyObj<GameService>;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should open modal when game is over', () => {
    (gameService.gameState as BehaviorSubject<any>).next({
      game_over: true,
      winner: 'white'
    });
    fixture.detectChanges();
    expect(component.isOpen).toBe(true);
    expect(component.winnerMessage).toContain('WHITE');
  });

  it('should close modal', () => {
    component.isOpen = true;
    component.close();
    expect(component.isOpen).toBe(false);
  });
});
