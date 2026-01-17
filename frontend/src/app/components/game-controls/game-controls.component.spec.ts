import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GameControlsComponent } from './game-controls.component';
import { GameService } from '../../services/game.service';
import { of } from 'rxjs';

describe('GameControlsComponent', () => {
  let component: GameControlsComponent;
  let fixture: ComponentFixture<GameControlsComponent>;
  let gameService: jasmine.SpyObj<GameService>;

  beforeEach(async () => {
    const gameServiceSpy = jasmine.createSpyObj('GameService', ['newGame'], {
      gameState: of(null)
    });

    await TestBed.configureTestingModule({
      imports: [GameControlsComponent],
      providers: [
        { provide: GameService, useValue: gameServiceSpy }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(GameControlsComponent);
    component = fixture.componentInstance;
    gameService = TestBed.inject(GameService) as jasmine.SpyObj<GameService>;
    gameService.newGame.and.returnValue(of({}));
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should create new game when newGame is called', () => {
    component.newGame();
    expect(gameService.newGame).toHaveBeenCalledWith(false);
  });

  it('should create custom game when newCustomGame is called', () => {
    component.newCustomGame();
    expect(gameService.newGame).toHaveBeenCalledWith(true);
  });

  it('should display message after creating game', (done) => {
    component.newGame();
    setTimeout(() => {
      expect(component.message).toContain('New game created');
      done();
    }, 100);
  });
});
