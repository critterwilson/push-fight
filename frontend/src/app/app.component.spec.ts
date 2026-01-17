import { TestBed } from '@angular/core/testing';
import { AppComponent } from './app.component';
import { GameService } from './services/game.service';
import { of } from 'rxjs';

describe('AppComponent', () => {
  let component: AppComponent;
  let fixture: any;

  beforeEach(async () => {
    const gameServiceSpy = jasmine.createSpyObj('GameService', [], {
      setupMode$: of(false),
      gameState: of(null)
    });

    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        { provide: GameService, useValue: gameServiceSpy }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(AppComponent);
    component = fixture.componentInstance;
  });

  it('should create the app', () => {
    expect(component).toBeTruthy();
  });

  it('should have gameService', () => {
    expect(component.gameService).toBeTruthy();
  });
});
