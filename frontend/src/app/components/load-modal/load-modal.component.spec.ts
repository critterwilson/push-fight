import { ComponentFixture, TestBed } from '@angular/core/testing';
import { LoadModalComponent } from './load-modal.component';
import { GameService } from '../../services/game.service';
import { of } from 'rxjs';

describe('LoadModalComponent', () => {
  let component: LoadModalComponent;
  let fixture: ComponentFixture<LoadModalComponent>;
  let gameService: jasmine.SpyObj<GameService>;

  beforeEach(async () => {
    const gameServiceSpy = jasmine.createSpyObj('GameService', ['loadGame', 'listSaves'], {
      gameState: of(null)
    });

    await TestBed.configureTestingModule({
      imports: [LoadModalComponent],
      providers: [
        { provide: GameService, useValue: gameServiceSpy }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(LoadModalComponent);
    component = fixture.componentInstance;
    gameService = TestBed.inject(GameService) as jasmine.SpyObj<GameService>;
    gameService.loadGame.and.returnValue(of({ message: 'Game loaded' }));
    gameService.listSaves.and.returnValue(of(['game1', 'game2']));
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should open modal and load saves', () => {
    component.open();
    expect(component.isOpen).toBe(true);
    expect(gameService.listSaves).toHaveBeenCalled();
  });

  it('should close modal', () => {
    component.isOpen = true;
    component.close();
    expect(component.isOpen).toBe(false);
  });

  it('should load game when filename is clicked', () => {
    component.load('test_game');
    expect(gameService.loadGame).toHaveBeenCalledWith('test_game');
  });
});
