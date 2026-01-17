import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameService } from '../../services/game.service';

@Component({
  selector: 'app-game-status',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="game-status" *ngIf="gameService.gameState | async as state">
      <div class="status-item">
        <span class="label">Current Player:</span>
        <span class="value" [class.white]="state.current_player === 'white'" 
              [class.brown]="state.current_player === 'brown'">
          {{ state.current_player | titlecase }}
        </span>
      </div>
      <div class="status-item" *ngIf="!state.setup_mode">
        <span class="label">Moves Made:</span>
        <span class="value">{{ state.moves_made }}/2</span>
      </div>
      <div class="status-item">
        <span class="label">Phase:</span>
        <span class="value" [class.push-phase]="!state.setup_mode && (state.moves_made >= 2 || !state.push_completed)">
          {{ getPhaseLabel(state) }}
        </span>
      </div>
    </div>
  `,
  styles: [`
    .game-status {
      display: flex;
      gap: 20px;
      justify-content: center;
      flex-wrap: wrap;
    }

    .status-item {
      display: flex;
      gap: 5px;
    }

    .label {
      font-weight: bold;
    }

    .value {
      padding: 2px 8px;
      border-radius: 4px;
      background: #f0f0f0;
    }

    .value.white {
      background: #fff;
      color: #333;
    }

    .value.brown {
      background: #8b4513;
      color: #fff;
    }

    .value.push-phase {
      background: #ff9800;
      color: white;
      font-weight: bold;
    }
  `]
})
export class GameStatusComponent {
  constructor(public gameService: GameService) {}

  getPhaseLabel(state: any): string {
    if (state.setup_mode) return 'Setup';
    if (state.moves_made >= 2 || !state.push_completed) return 'Push Phase';
    return 'Move Phase';
  }
}
