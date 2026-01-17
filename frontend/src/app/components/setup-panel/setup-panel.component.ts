import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { GameService } from '../../services/game.service';

@Component({
  selector: 'app-setup-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="setup-panel" *ngIf="gameService.setupMode$ | async">
      <h2>Place Your Pieces</h2>
      <div class="placement-info">
        <div class="team-section">
          <h3>White Team</h3>
          <div class="piece-inventory">
            <div class="inventory-item">
              <span>Square Pieces:</span>
              <span>{{ (gameService.gameState | async)?.placement_status?.white?.squares || 0 }}/3</span>
            </div>
            <div class="inventory-item">
              <span>Round Pieces:</span>
              <span>{{ (gameService.gameState | async)?.placement_status?.white?.rounds || 0 }}/2</span>
            </div>
          </div>
        </div>
        <div class="team-section">
          <h3>Brown Team</h3>
          <div class="piece-inventory">
            <div class="inventory-item">
              <span>Square Pieces:</span>
              <span>{{ (gameService.gameState | async)?.placement_status?.brown?.squares || 0 }}/3</span>
            </div>
            <div class="inventory-item">
              <span>Round Pieces:</span>
              <span>{{ (gameService.gameState | async)?.placement_status?.brown?.rounds || 0 }}/2</span>
            </div>
          </div>
        </div>
      </div>
      <div class="placement-controls">
        <div class="piece-selector">
          <label>Piece Type:</label>
          <select [(ngModel)]="selectedShape">
            <option value="square">Square</option>
            <option value="round">Round</option>
          </select>
        </div>
        <div class="team-selector">
          <label>Team:</label>
          <select [(ngModel)]="selectedTeam">
            <option value="white">White</option>
            <option value="brown">Brown</option>
          </select>
        </div>
        <button class="btn btn-secondary" (click)="removeMode = !removeMode">
          {{ removeMode ? 'Cancel Remove' : 'Remove Piece' }}
        </button>
        <button 
          class="btn btn-primary" 
          [disabled]="!canStart()"
          (click)="startGame()"
        >
          Start Game
        </button>
      </div>
      <div class="message" *ngIf="message">{{ message }}</div>
    </div>
  `,
  styles: [`
    .setup-panel {
      padding: 20px;
      border: 2px solid #333;
      border-radius: 8px;
      background: #f9f9f9;
    }

    .placement-info {
      display: flex;
      gap: 40px;
      justify-content: center;
      margin: 20px 0;
    }

    .team-section h3 {
      margin-bottom: 10px;
    }

    .inventory-item {
      display: flex;
      justify-content: space-between;
      margin: 5px 0;
    }

    .placement-controls {
      display: flex;
      gap: 10px;
      align-items: center;
      justify-content: center;
      flex-wrap: wrap;
    }

    .piece-selector, .team-selector {
      display: flex;
      gap: 5px;
      align-items: center;
    }

    select {
      padding: 5px;
      border-radius: 4px;
    }
  `]
})
export class SetupPanelComponent {
  selectedShape: string = 'square';
  selectedTeam: string = 'white';
  removeMode: boolean = false;
  message: string = '';

  constructor(public gameService: GameService) {
    // Expose to window for game board access (better would be a shared service)
    (window as any).setupPanelRef = this;
  }

  canStart(): boolean {
    const state = this.gameService.getCurrentState();
    if (!state?.placement_status) return false;
    const white = state.placement_status.white;
    const brown = state.placement_status.brown;
    return white.squares === 3 && white.rounds === 2 &&
           brown.squares === 3 && brown.rounds === 2;
  }

  startGame(): void {
    this.gameService.startGame().subscribe({
      next: () => this.showMessage('Game started!'),
      error: (err) => this.showMessage('Error: ' + err.error?.error)
    });
  }

  private showMessage(msg: string): void {
    this.message = msg;
    setTimeout(() => this.message = '', 3000);
  }
}
