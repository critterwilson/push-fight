import { Component, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameService } from '../../services/game.service';
import { SaveModalComponent } from '../save-modal/save-modal.component';
import { LoadModalComponent } from '../load-modal/load-modal.component';

@Component({
  selector: 'app-game-controls',
  standalone: true,
  imports: [CommonModule, SaveModalComponent, LoadModalComponent],
  template: `
    <div class="controls-panel">
      <div class="control-group">
        <button class="btn btn-primary" (click)="newGame()">New Game</button>
        <button class="btn btn-secondary" (click)="newCustomGame()">Custom Setup</button>
      </div>
      <div class="control-group">
        <button class="btn btn-secondary" (click)="saveModal?.open()">Save Game</button>
        <button class="btn btn-secondary" (click)="loadModal?.open()">Load Game</button>
      </div>
      <div class="message" *ngIf="message">{{ message }}</div>
    </div>
    <app-save-modal #saveModal></app-save-modal>
    <app-load-modal #loadModal></app-load-modal>
  `,
  styles: [`
    .controls-panel {
      display: flex;
      flex-direction: column;
      gap: 10px;
      align-items: center;
    }

    .control-group {
      display: flex;
      gap: 10px;
    }

    .btn {
      padding: 10px 20px;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
      transition: background 0.2s;
    }

    .btn-primary {
      background: #2196F3;
      color: white;
    }

    .btn-primary:hover {
      background: #1976D2;
    }

    .btn-secondary {
      background: #757575;
      color: white;
    }

    .btn-secondary:hover {
      background: #616161;
    }

    .message {
      margin-top: 10px;
      padding: 10px;
      border-radius: 4px;
      background: #e3f2fd;
    }
  `]
})
export class GameControlsComponent {
  @ViewChild('saveModal') saveModal?: SaveModalComponent;
  @ViewChild('loadModal') loadModal?: LoadModalComponent;
  message: string = '';

  constructor(private gameService: GameService) {}

  newGame(): void {
    this.gameService.newGame(false).subscribe({
      next: () => this.showMessage('New game created!'),
      error: (err) => this.showMessage('Error: ' + err.error?.error)
    });
  }

  newCustomGame(): void {
    this.gameService.newGame(true).subscribe({
      next: () => this.showMessage('Custom game setup started!'),
      error: (err) => this.showMessage('Error: ' + err.error?.error)
    });
  }

  private showMessage(msg: string): void {
    this.message = msg;
    setTimeout(() => this.message = '', 3000);
  }
}
