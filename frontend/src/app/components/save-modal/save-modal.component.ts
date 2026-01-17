import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { GameService } from '../../services/game.service';

@Component({
  selector: 'app-save-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="modal" [class.show]="isOpen" (click)="closeOnBackdrop($event)">
      <div class="modal-content" (click)="$event.stopPropagation()">
        <span class="close" (click)="close()">&times;</span>
        <h2>Save Game</h2>
        <div class="modal-body">
          <label for="save-filename">Filename:</label>
          <input type="text" id="save-filename" [(ngModel)]="filename" placeholder="game1" />
          <div class="existing-saves" *ngIf="existingSaves.length > 0">
            <h3>Existing Saves:</h3>
            <ul>
              <li *ngFor="let save of existingSaves" (click)="filename = save">{{ save }}</li>
            </ul>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" (click)="save()">Save</button>
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

    .close {
      position: absolute;
      right: 20px;
      top: 15px;
      font-size: 28px;
      cursor: pointer;
    }

    .modal-body {
      margin: 20px 0;
    }

    input {
      width: 100%;
      padding: 8px;
      margin-top: 5px;
      border: 1px solid #ccc;
      border-radius: 4px;
    }

    .existing-saves ul {
      list-style: none;
      padding: 0;
      max-height: 200px;
      overflow-y: auto;
    }

    .existing-saves li {
      padding: 5px;
      cursor: pointer;
      border-bottom: 1px solid #eee;
    }

    .existing-saves li:hover {
      background: #f0f0f0;
    }

    .modal-footer {
      display: flex;
      gap: 10px;
      justify-content: flex-end;
    }
  `]
})
export class SaveModalComponent {
  isOpen: boolean = false;
  filename: string = '';
  existingSaves: string[] = [];

  constructor(private gameService: GameService) {
    this.loadSaves();
  }

  open(): void {
    this.isOpen = true;
    this.loadSaves();
  }

  close(): void {
    this.isOpen = false;
    this.filename = '';
  }

  closeOnBackdrop(event: Event): void {
    if (event.target === event.currentTarget) {
      this.close();
    }
  }

  save(): void {
    if (!this.filename.trim()) {
      alert('Please enter a filename');
      return;
    }
    this.gameService.saveGame(this.filename).subscribe({
      next: () => {
        alert('Game saved!');
        this.close();
      },
      error: (err) => alert('Error: ' + err.error?.error)
    });
  }

  loadSaves(): void {
    this.gameService.listSaves().subscribe({
      next: (saves) => this.existingSaves = saves,
      error: () => this.existingSaves = []
    });
  }
}
