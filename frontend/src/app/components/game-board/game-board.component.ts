import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GameService } from '../../services/game.service';

@Component({
  selector: 'app-game-board',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="board-container">
      <div class="push-phase-indicator" *ngIf="isPushPhase() && !isSetupMode()">
        <div class="push-banner">
          <span>⚠️ PUSH PHASE - Select a square piece to push</span>
        </div>
      </div>
      <div class="game-board">
        <div 
          *ngFor="let row of boardCells; let y = index" 
          class="board-row"
        >
          <div
            *ngFor="let cell of row; let x = index"
            class="board-cell"
            [class.kill-zone]="cell.isKillZone"
            [class.playable]="cell.isPlayable"
            [class.empty-kill-zone]="cell.isKillZone && !cell.piece"
            [class.selected]="isSelected(y, x)"
            [class.valid-move]="isValidMove(y, x)"
            [class.push-target]="isPushTarget(y, x)"
            [class.has-piece]="cell.piece"
            [class.anchored]="isAnchored(y, x)"
            [class.centerline-top]="y === 4"
            [class.centerline-bottom]="y === 5"
            (click)="onCellClick(y, x)"
          >
            <div *ngIf="cell.piece" class="piece" [ngClass]="getPieceClasses(cell.piece)">
              <div class="piece-inner">
                <span class="piece-shape">{{ cell.piece.shape === 'square' ? '■' : '●' }}</span>
              </div>
            </div>
            <div *ngIf="isAnchored(y, x)" class="anchor-indicator">⚓</div>
          </div>
        </div>
      </div>
      <div class="push-direction-buttons" *ngIf="isPushMode() && hasSelectedSquarePiece()">
        <h3>Select Push Direction:</h3>
        <div class="direction-grid">
          <button class="dir-btn" (click)="selectPushDirection(-1, 0)" [disabled]="!canPushInDirection(-1, 0)">
            ↑ Up
          </button>
          <div class="direction-row">
            <button class="dir-btn" (click)="selectPushDirection(0, -1)" [disabled]="!canPushInDirection(0, -1)">
              ← Left
            </button>
            <button class="dir-btn" (click)="selectPushDirection(0, 1)" [disabled]="!canPushInDirection(0, 1)">
              Right →
            </button>
          </div>
          <button class="dir-btn" (click)="selectPushDirection(1, 0)" [disabled]="!canPushInDirection(1, 0)">
            ↓ Down
          </button>
        </div>
        <button class="btn-cancel" (click)="cancelPush()">Cancel</button>
      </div>
      <div class="board-legend">
        <div class="legend-item">
          <div class="legend-piece white-square">
            <div class="legend-piece-inner">■</div>
          </div>
          <span>White Square</span>
        </div>
        <div class="legend-item">
          <div class="legend-piece white-round">
            <div class="legend-piece-inner">●</div>
          </div>
          <span>White Round</span>
        </div>
        <div class="legend-item">
          <div class="legend-piece brown-square">
            <div class="legend-piece-inner">■</div>
          </div>
          <span>Brown Square</span>
        </div>
        <div class="legend-item">
          <div class="legend-piece brown-round">
            <div class="legend-piece-inner">●</div>
          </div>
          <span>Brown Round</span>
        </div>
        <div class="legend-item">
          <div class="legend-anchor">⚓</div>
          <span>Anchored</span>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .board-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 20px;
    }

    .game-board {
      display: grid;
      grid-template-rows: repeat(10, 60px);
      grid-template-columns: repeat(4, 60px);
      gap: 3px;
      border: 3px solid #333;
      padding: 8px;
      background: #e8e8e8;
      border-radius: 4px;
      box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }

    .board-cell {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.2s;
      min-height: 60px;
      min-width: 60px;
    }

    .board-cell.playable {
      background: #f9f9f9;
      border: 2px solid #bdbdbd;
      box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
    }

    .board-cell.kill-zone {
      background: #1a1a1a;
      border: 2px solid #0a0a0a;
      cursor: not-allowed;
    }

    .board-cell.empty-kill-zone {
      background: #1a1a1a;
      opacity: 0.7;
    }

    .board-cell.kill-zone:hover {
      background: #1a1a1a;
      transform: none;
    }

    .board-cell.centerline-top {
      border-top: 3px solid #ff6b6b;
    }

    .board-cell.centerline-bottom {
      border-bottom: 3px solid #ff6b6b;
    }

    .board-cell.playable:hover:not(.has-piece) {
      background: #e8f5e9;
      border-color: #4caf50;
    }

    .board-cell.playable.has-piece:hover {
      background: #f9f9f9;
    }

    .board-cell.selected {
      background: #fff9c4 !important;
      border: 3px solid #ff9800 !important;
      box-shadow: 0 0 10px rgba(255, 152, 0, 0.6);
      z-index: 10;
    }

    .board-cell.valid-move {
      background: #c8e6c9 !important;
      border: 2px dashed #4caf50 !important;
      box-shadow: 0 0 8px rgba(76, 175, 80, 0.4);
    }

    .board-cell.valid-move:hover {
      background: #a5d6a7 !important;
      border-color: #388e3c !important;
    }

    .board-cell.has-piece:hover {
      transform: scale(1.05);
      z-index: 5;
    }

    .board-cell.has-piece .piece {
      transition: transform 0.2s;
    }

    .board-cell.has-piece:hover .piece {
      transform: scale(1.1);
      box-shadow: 0 4px 8px rgba(0,0,0,0.4);
    }

    .piece {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      border-radius: 4px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }

    .piece-inner {
      width: 85%;
      height: 85%;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: inherit;
      border: 2px solid rgba(0,0,0,0.3);
    }

    .piece-shape {
      font-size: 32px;
      line-height: 1;
      font-weight: bold;
    }

    .piece.white-square {
      background: linear-gradient(135deg, #ffffff 0%, #e0e0e0 100%);
      border: 3px solid #ffffff;
    }

    .piece.white-square .piece-inner {
      background: #ffffff;
      border-color: #bdbdbd;
    }

    .piece.white-square .piece-shape {
      color: #424242;
      text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }

    .piece.white-round {
      background: linear-gradient(135deg, #ffffff 0%, #e0e0e0 100%);
      border-radius: 50%;
      border: 3px solid #ffffff;
    }

    .piece.white-round .piece-inner {
      background: #ffffff;
      border-radius: 50%;
      border-color: #bdbdbd;
    }

    .piece.white-round .piece-shape {
      color: #424242;
      text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }

    .piece.brown-square {
      background: linear-gradient(135deg, #8b4513 0%, #654321 100%);
      border: 3px solid #5d4037;
    }

    .piece.brown-square .piece-inner {
      background: linear-gradient(135deg, #a0522d 0%, #8b4513 100%);
      border-color: #5d4037;
    }

    .piece.brown-square .piece-shape {
      color: #ffffff;
      text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
    }

    .piece.brown-round {
      background: linear-gradient(135deg, #8b4513 0%, #654321 100%);
      border-radius: 50%;
      border: 3px solid #5d4037;
    }

    .piece.brown-round .piece-inner {
      background: radial-gradient(circle, #a0522d 0%, #8b4513 100%);
      border-radius: 50%;
      border-color: #5d4037;
    }

    .piece.brown-round .piece-shape {
      color: #ffffff;
      text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
    }

    .anchor-indicator {
      position: absolute;
      top: 4px;
      right: 4px;
      font-size: 16px;
      color: #f44336;
      background: rgba(255, 255, 255, 0.9);
      border-radius: 50%;
      width: 20px;
      height: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 2px solid #f44336;
      z-index: 20;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }

    .board-legend {
      display: flex;
      gap: 20px;
      flex-wrap: wrap;
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 5px;
    }

    .legend-piece {
      width: 30px;
      height: 30px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 4px;
      border: 2px solid rgba(0,0,0,0.2);
      box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }

    .legend-piece.white-square {
      background: #ffffff;
      border-color: #bdbdbd;
    }

    .legend-piece.white-round {
      background: #ffffff;
      border-radius: 50%;
      border-color: #bdbdbd;
    }

    .legend-piece.brown-square {
      background: linear-gradient(135deg, #a0522d 0%, #8b4513 100%);
      border-color: #5d4037;
    }

    .legend-piece.brown-round {
      background: radial-gradient(circle, #a0522d 0%, #8b4513 100%);
      border-radius: 50%;
      border-color: #5d4037;
    }

    .legend-piece-inner {
      font-size: 18px;
      font-weight: bold;
    }

    .legend-piece.white-square .legend-piece-inner,
    .legend-piece.white-round .legend-piece-inner {
      color: #424242;
    }

    .legend-piece.brown-square .legend-piece-inner,
    .legend-piece.brown-round .legend-piece-inner {
      color: #ffffff;
      text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
    }

    .legend-anchor {
      width: 30px;
      height: 30px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      background: rgba(255, 255, 255, 0.9);
      border: 2px solid #f44336;
      border-radius: 50%;
      color: #f44336;
    }

    .push-phase-indicator {
      width: 100%;
      margin-bottom: 10px;
    }

    .push-banner {
      background: #ff9800;
      color: white;
      padding: 10px 20px;
      border-radius: 4px;
      text-align: center;
      font-weight: bold;
      box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }

    .board-cell.push-target {
      background: #ffeb3b;
      border: 2px dashed #ff9800;
      cursor: pointer;
    }

    .push-direction-buttons {
      margin-top: 20px;
      padding: 20px;
      background: #f9f9f9;
      border-radius: 8px;
      border: 2px solid #333;
      text-align: center;
    }

    .push-direction-buttons h3 {
      margin-bottom: 15px;
      color: #333;
    }

    .direction-grid {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
      margin-bottom: 15px;
    }

    .direction-row {
      display: flex;
      gap: 10px;
    }

    .dir-btn {
      padding: 15px 25px;
      font-size: 16px;
      font-weight: bold;
      border: 2px solid #333;
      border-radius: 4px;
      background: #2196F3;
      color: white;
      cursor: pointer;
      transition: all 0.2s;
      min-width: 100px;
    }

    .dir-btn:hover:not(:disabled) {
      background: #1976D2;
      transform: scale(1.05);
    }

    .dir-btn:disabled {
      background: #ccc;
      color: #666;
      cursor: not-allowed;
      opacity: 0.6;
    }

    .btn-cancel {
      padding: 10px 20px;
      font-size: 14px;
      border: 1px solid #666;
      border-radius: 4px;
      background: #757575;
      color: white;
      cursor: pointer;
    }

    .btn-cancel:hover {
      background: #616161;
    }
  `]
})
export class GameBoardComponent implements OnInit {
  boardCells: any[][] = [];
  private selectedPushPiece: [number, number] | null = null;

  constructor(public gameService: GameService, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    // Initial board update
    this.updateBoard();
    
    // Subscribe to game state changes
    this.gameService.gameState.subscribe(() => {
      this.updateBoard();
      this.cdr.detectChanges();
      // Clear push selection if we're no longer in push mode
      if (!this.isPushPhase()) {
        this.selectedPushPiece = null;
      }
    });
  }

  updateBoard(): void {
    const state = this.gameService.getCurrentState();
    
    // Default board layout (kill zones = -1, playable = 0)
    const defaultGrid = [
      [-1, -1, -1, -1], // Row 0: North Kill Zone
      [-1,  0,  0, -1], // Row 1
      [ 0,  0,  0, -1], // Row 2
      [ 0,  0,  0,  0], // Row 3
      [ 0,  0,  0,  0], // Row 4 (White starts N of center)
      // --- Center Line ---
      [ 0,  0,  0,  0], // Row 5 (Brown starts S of center)
      [ 0,  0,  0,  0], // Row 6
      [-1,  0,  0,  0], // Row 7
      [-1,  0,  0, -1], // Row 8
      [-1, -1, -1, -1]  // Row 9: South Kill Zone
    ];

    if (!state) {
      // Initialize board with default layout
      this.boardCells = defaultGrid.map((row, y) => 
        row.map((cell, x) => ({ 
          isKillZone: cell === -1, 
          isPlayable: cell === 0,
          piece: null 
        }))
      );
      return;
    }

    // Create new array to trigger change detection
    const newBoardCells: any[][] = [];
    const grid = state.board.grid || defaultGrid;
    
    for (let y = 0; y < 10; y++) {
      const row = [];
      for (let x = 0; x < 4; x++) {
        const isKillZone = grid[y]?.[x] === -1;
        const isPlayable = grid[y]?.[x] === 0;
        // Pieces can only exist on playable spaces (0), not kill zones (-1)
        const piece = (isPlayable && state.board.pieces[y]?.[x]) ? state.board.pieces[y][x] : null;
        row.push({ isKillZone, isPlayable, piece });
      }
      newBoardCells.push(row);
    }
    this.boardCells = newBoardCells;
  }

  onCellClick(y: number, x: number): void {
    const state = this.gameService.getCurrentState();
    if (!state) return;

    if (state.setup_mode) {
      this.handleSetupClick(y, x);
    } else {
      this.handleGameClick(y, x);
    }
  }

  handleSetupClick(y: number, x: number): void {
    const state = this.gameService.getCurrentState();
    if (!state) return;

    // Get setup panel component reference (will be injected via service or event)
    // For now, emit an event or use a service method
    const setupPanel = (window as any).setupPanelRef;
    if (setupPanel) {
      if (setupPanel.removeMode) {
        this.gameService.removePiece(y, x).subscribe();
      } else {
        this.gameService.placePiece(
          y, 
          x, 
          setupPanel.selectedTeam, 
          setupPanel.selectedShape
        ).subscribe();
      }
    }
  }

  handleGameClick(y: number, x: number): void {
    const state = this.gameService.getCurrentState();
    if (!state || state.game_over) return;

    const isPushPhase = this.isPushPhase();
    let selectedPos: [number, number] | null = null;
    this.gameService.selectedPiece.subscribe(pos => {
      selectedPos = pos;
    }).unsubscribe();

    if (isPushPhase) {
      // Push phase: select square piece for pushing
      if (!selectedPos) {
        const piece = state.board.pieces[y]?.[x];
        if (piece && piece.team === state.current_player && piece.shape === 'square') {
          this.gameService.selectPiece(y, x, 'push');
          this.selectedPushPiece = [y, x];
        }
      } else if (selectedPos !== null) {
        // Already have a piece selected for pushing
        // Check if clicking adjacent cell for direction
        const [sy, sx] = selectedPos as [number, number];
        const dy = y - sy;
        const dx = x - sx;
        
        // If clicking the same cell, deselect
        if (dy === 0 && dx === 0) {
          this.gameService.clearSelection();
          this.selectedPushPiece = null;
        } else if ((Math.abs(dy) === 1 && dx === 0) || (Math.abs(dx) === 1 && dy === 0)) {
          // Adjacent cell clicked - use as direction
          this.selectPushDirection(dy, dx);
        }
      }
    } else {
      // Move phase: normal piece movement
      if (!selectedPos) {
        // Select piece
        const piece = state.board.pieces[y]?.[x];
        if (piece && piece.team === state.current_player) {
          this.gameService.selectPiece(y, x, 'move');
        }
      } else if (selectedPos !== null) {
        // Move or push
        const [sy, sx] = selectedPos as [number, number];
        if (sy === y && sx === x) {
          this.gameService.clearSelection();
        } else {
          // Check if it's a move
          this.gameService.validMoves.subscribe(moves => {
            const isValidMove = moves.some(([my, mx]) => my === y && mx === x);
            if (isValidMove) {
              this.gameService.movePiece([sy, sx], [y, x]).subscribe({
                next: () => {
                  // Move successful - board will update via gameState subscription
                },
                error: (err) => {
                  console.error('Move failed:', err);
                  this.gameService.clearSelection();
                }
              });
            } else {
              // Not a valid move - clear selection
              this.gameService.clearSelection();
            }
          }).unsubscribe();
        }
      }
    }
  }

  isPushPhase(): boolean {
    const state = this.gameService.getCurrentState();
    if (!state || state.setup_mode || state.game_over) return false;
    return state.moves_made >= 2 || !state.push_completed;
  }

  isSetupMode(): boolean {
    const state = this.gameService.getCurrentState();
    return state?.setup_mode || false;
  }

  isPushMode(): boolean {
    return this.isPushPhase() && this.selectedPushPiece !== null;
  }

  hasSelectedSquarePiece(): boolean {
    if (!this.selectedPushPiece) return false;
    const state = this.gameService.getCurrentState();
    if (!state) return false;
    const [y, x] = this.selectedPushPiece;
    const piece = state.board.pieces[y]?.[x];
    return piece !== null && piece.shape === 'square' && piece.team === state.current_player;
  }

  canPushInDirection(dy: number, dx: number): boolean {
    if (!this.selectedPushPiece) return false;
    const [y, x] = this.selectedPushPiece;
    const state = this.gameService.getCurrentState();
    if (!state) return false;
    
    // Check if direction is valid (adjacent only)
    if (Math.abs(dy) + Math.abs(dx) !== 1) return false;
    
    // Check if target is on board (basic validation)
    const targetY = y + dy;
    const targetX = x + dx;
    if (targetY < 0 || targetY >= 10 || targetX < 0 || targetX >= 4) {
      return false; // Would hit side rail
    }
    
    return true;
  }

  selectPushDirection(dy: number, dx: number): void {
    if (!this.selectedPushPiece) return;
    
    const [y, x] = this.selectedPushPiece;
    this.gameService.pushPiece([y, x], [dy, dx]).subscribe({
      next: () => {
        this.selectedPushPiece = null;
      },
      error: (err) => {
        console.error('Push failed:', err);
        // Keep selection for retry
      }
    });
  }

  cancelPush(): void {
    this.gameService.clearSelection();
    this.selectedPushPiece = null;
  }

  isPushTarget(y: number, x: number): boolean {
    if (!this.selectedPushPiece) return false;
    const [sy, sx] = this.selectedPushPiece;
    const dy = y - sy;
    const dx = x - sx;
    // Highlight adjacent cells as potential push targets
    return (Math.abs(dy) === 1 && dx === 0) || (Math.abs(dx) === 1 && dy === 0);
  }

  isSelected(y: number, x: number): boolean {
    let selected: [number, number] | null = null;
    this.gameService.selectedPiece.subscribe(pos => selected = pos).unsubscribe();
    return selected !== null && selected[0] === y && selected[1] === x;
  }

  isValidMove(y: number, x: number): boolean {
    let moves: [number, number][] = [];
    this.gameService.validMoves.subscribe(m => moves = m).unsubscribe();
    return moves.some(([my, mx]) => my === y && mx === x);
  }

  isAnchored(y: number, x: number): boolean {
    const state = this.gameService.getCurrentState();
    if (!state) return false;
    const anchor = state.board.anchor_pos;
    return anchor[0] === y && anchor[1] === x;
  }

  getPieceClasses(piece: any): string {
    return `${piece.team} ${piece.shape}`;
  }
}
