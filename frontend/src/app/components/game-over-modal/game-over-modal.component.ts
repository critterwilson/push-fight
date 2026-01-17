import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameService } from '../../services/game.service';

@Component({
  selector: 'app-game-over-modal',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="modal" [class.show]="isOpen" (click)="closeOnBackdrop($event)">
      <div class="modal-content" (click)="$event.stopPropagation()">
        <h2>Game Over!</h2>
        <div class="modal-body">
          <p class="winner-message">{{ winnerMessage }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" (click)="close()">Close</button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .modal {
      display: none;
      position: fixed;
      z-index: 1000;
      left: 0;
      top: 0;
      width: 100%;
      height: 100%;
      background: rgba(0,0,0,0.5);
    }

    .modal.show {
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .modal-content {
      background: white;
      padding: 20px;
      border-radius: 8px;
      max-width: 400px;
      width: 90%;
    }

    .winner-message {
      font-size: 18px;
      font-weight: bold;
      text-align: center;
      margin: 20px 0;
    }
  `]
})
export class GameOverModalComponent {
  isOpen: boolean = false;
  winnerMessage: string = '';

  constructor(private gameService: GameService) {
    this.gameService.gameState.subscribe(state => {
      if (state?.game_over && state.winner) {
        this.winnerMessage = `${state.winner.toUpperCase()} team wins!`;
        this.isOpen = true;
      }
    });
  }

  close(): void {
    this.isOpen = false;
  }

  closeOnBackdrop(event: Event): void {
    if (event.target === event.currentTarget) {
      this.close();
    }
  }
}
