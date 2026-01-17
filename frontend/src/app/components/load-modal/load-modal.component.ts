import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameService } from '../../services/game.service';

@Component({
  selector: 'app-load-modal',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="modal" [class.show]="isOpen" (click)="closeOnBackdrop($event)">
      <div class="modal-content" (click)="$event.stopPropagation()">
        <span class="close" (click)="close()">&times;</span>
        <h2>Load Game</h2>
        <div class="modal-body">
          <div class="saves-list" *ngIf="saves.length > 0">
            <h3>Saved Games:</h3>
            <ul>
              <li *ngFor="let save of saves" (click)="load(save)">{{ save }}</li>
            </ul>
          </div>
          <div *ngIf="saves.length === 0" class="no-saves">
            No saved games found.
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" (click)="close()">Cancel</button>
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
      max-width: 500px;
      width: 90%;
      position: relative;
    }

    .saves-list ul {
      list-style: none;
      padding: 0;
      max-height: 300px;
      overflow-y: auto;
    }

    .saves-list li {
      padding: 10px;
      cursor: pointer;
      border-bottom: 1px solid #eee;
    }

    .saves-list li:hover {
      background: #f0f0f0;
    }

    .no-saves {
      padding: 20px;
      text-align: center;
      color: #666;
    }
  `]
})
export class LoadModalComponent {
  isOpen: boolean = false;
  saves: string[] = [];

  constructor(private gameService: GameService) {}

  open(): void {
    this.isOpen = true;
    this.loadSaves();
  }

  close(): void {
    this.isOpen = false;
  }

  closeOnBackdrop(event: Event): void {
    if (event.target === event.currentTarget) {
      this.close();
    }
  }

  load(filename: string): void {
    this.gameService.loadGame(filename).subscribe({
      next: () => {
        alert('Game loaded!');
        this.close();
      },
      error: (err) => alert('Error: ' + err.error?.error)
    });
  }

  loadSaves(): void {
    this.gameService.listSaves().subscribe({
      next: (saves) => this.saves = saves,
      error: () => this.saves = []
    });
  }
}
