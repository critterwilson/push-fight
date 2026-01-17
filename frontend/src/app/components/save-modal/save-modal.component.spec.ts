import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SaveModalComponent } from './save-modal.component';
import { GameService } from '../../services/game.service';
import { of } from 'rxjs';

describe('SaveModalComponent', () => {
  let component: SaveModalComponent;
  let fixture: ComponentFixture<SaveModalComponent>;
  let gameService: jasmine.SpyObj<GameService>;

  beforeEach(async () => {
    const gameServiceSpy = jasmine.createSpyObj('GameService', ['saveGame', 'listSaves'], {
      gameState: of(null)
    });

    await TestBed.configureTestingModule({
      imports: [SaveModalComponent],
      providers: [
        { provide: GameService, useValue: gameServiceSpy }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(SaveModalComponent);
    component = fixture.componentInstance;
    gameService = TestBed.inject(GameService) as jasmine.SpyObj<GameService>;
    gameService.saveGame.and.returnValue(of({ message: 'Game saved' }));
    gameService.listSaves.and.returnValue(of(['game1', 'game2']));
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should open modal', () => {
    component.open();
    expect(component.isOpen).toBe(true);
  });

  it('should close modal', () => {
    component.isOpen = true;
    component.close();
    expect(component.isOpen).toBe(false);
    expect(component.filename).toBe('');
  });

  it('should load saves when opened', () => {
    component.open();
    expect(gameService.listSaves).toHaveBeenCalled();
  });

  it('should save game with filename', () => {
    component.filename = 'test_game';
    component.save();
    expect(gameService.saveGame).toHaveBeenCalledWith('test_game');
  });

  it('should not save with empty filename', () => {
    spyOn(window, 'alert');
    component.filename = '';
    component.save();
    expect(window.alert).toHaveBeenCalledWith('Please enter a filename');
    expect(gameService.saveGame).not.toHaveBeenCalled();
  });

  it('should close on backdrop click', () => {
    component.isOpen = true;
    const event = new MouseEvent('click');
    Object.defineProperty(event, 'target', { value: fixture.nativeElement.querySelector('.modal') });
    component.closeOnBackdrop(event);
    expect(component.isOpen).toBe(false);
  });
});
