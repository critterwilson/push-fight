import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameBoardComponent } from './components/game-board/game-board.component';
import { GameControlsComponent } from './components/game-controls/game-controls.component';
import { GameStatusComponent } from './components/game-status/game-status.component';
import { SetupPanelComponent } from './components/setup-panel/setup-panel.component';
import { SaveModalComponent } from './components/save-modal/save-modal.component';
import { LoadModalComponent } from './components/load-modal/load-modal.component';
import { GameOverModalComponent } from './components/game-over-modal/game-over-modal.component';
import { GameService } from './services/game.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    GameBoardComponent,
    GameControlsComponent,
    GameStatusComponent,
    SetupPanelComponent,
    GameOverModalComponent
  ],
  template: `
    <div class="container">
      <header>
        <h1>Push Fight</h1>
        <app-game-status></app-game-status>
      </header>

      <main>
        <div class="game-area">
          <app-setup-panel *ngIf="gameService.setupMode$ | async"></app-setup-panel>
          <app-game-board></app-game-board>
          <app-game-controls></app-game-controls>
        </div>
      </main>
    </div>

    <app-game-over-modal></app-game-over-modal>
  `,
  styles: [`
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px;
    }

    header {
      text-align: center;
      margin-bottom: 20px;
    }

    h1 {
      color: #333;
      margin-bottom: 10px;
    }

    .game-area {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
  `]
})
export class AppComponent implements OnInit {
  constructor(public gameService: GameService) {}

  ngOnInit(): void {
    // Initialize by trying to load existing game state
    // If no game exists, user can create a new one
    this.gameService.loadGameState();
  }
}
