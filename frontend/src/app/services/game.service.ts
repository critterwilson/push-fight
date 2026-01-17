import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';
import { tap, map } from 'rxjs/operators';

export interface GameState {
  board: {
    grid: number[][];
    pieces: (Piece | null)[][];
    anchor_pos: [number | null, number | null];
  };
  current_player: string;
  setup_mode: boolean;
  moves_made: number;
  push_completed: boolean;
  game_over: boolean;
  winner: string | null;
  placement_status?: {
    white: { squares: number; rounds: number; total: number };
    brown: { squares: number; rounds: number; total: number };
  };
}

export interface Piece {
  team: string;
  shape: string;
}

@Injectable({
  providedIn: 'root'
})
export class GameService {
  private apiUrl = '/api';
  private gameState$ = new BehaviorSubject<GameState | null>(null);
  private selectedPiece$ = new BehaviorSubject<[number, number] | null>(null);
  private validMoves$ = new BehaviorSubject<[number, number][]>([]);
  private actionMode$ = new BehaviorSubject<'move' | 'push' | 'place' | null>(null);

  constructor(private http: HttpClient) {
    this.loadGameState();
  }

  // Observables
  get gameState(): Observable<GameState | null> {
    return this.gameState$.asObservable();
  }

  get setupMode$(): Observable<boolean> {
    return new Observable(observer => {
      this.gameState$.subscribe(state => {
        observer.next(state?.setup_mode ?? false);
      });
    });
  }

  get selectedPiece(): Observable<[number, number] | null> {
    return this.selectedPiece$.asObservable();
  }

  get validMoves(): Observable<[number, number][]> {
    return this.validMoves$.asObservable();
  }

  get actionMode(): Observable<'move' | 'push' | 'place' | null> {
    return this.actionMode$.asObservable();
  }

  get isPushPhase$(): Observable<boolean> {
    return new Observable(observer => {
      this.gameState$.subscribe(state => {
        if (!state || state.setup_mode || state.game_over) {
          observer.next(false);
          return;
        }
        // Push phase: when moves_made >= 2 or push_completed is false but can_move is false
        const isPushPhase = state.moves_made >= 2 || !state.push_completed;
        observer.next(isPushPhase);
      });
    });
  }

  get canMove$(): Observable<boolean> {
    return new Observable(observer => {
      this.gameState$.subscribe(state => {
        if (!state || state.setup_mode || state.game_over) {
          observer.next(false);
          return;
        }
        observer.next(state.moves_made < 2 && !state.push_completed);
      });
    });
  }

  // API Methods
  loadGameState(): void {
    this.http.get<GameState>(`${this.apiUrl}/game/state`).subscribe({
      next: (state: GameState) => this.gameState$.next(state),
      error: () => this.gameState$.next(null)
    });
  }

  newGame(customPlacement: boolean = false): Observable<any> {
    return this.http.post(`${this.apiUrl}/game/new`, { custom_placement: customPlacement })
      .pipe(tap(() => this.loadGameState()));
  }

  movePiece(from: [number, number], to: [number, number]): Observable<any> {
    return this.http.post(`${this.apiUrl}/game/move`, { from, to })
      .pipe(tap(() => {
        this.loadGameState();
        this.clearSelection();
      }));
  }

  pushPiece(piece: [number, number], direction: [number, number]): Observable<any> {
    return this.http.post(`${this.apiUrl}/game/push`, { piece, direction })
      .pipe(tap(() => {
        this.loadGameState();
        this.clearSelection();
      }));
  }

  placePiece(y: number, x: number, team: string, shape: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/game/place`, { y, x, team, shape })
      .pipe(tap(() => this.loadGameState()));
  }

  removePiece(y: number, x: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/game/remove`, { y, x })
      .pipe(tap(() => this.loadGameState()));
  }

  startGame(): Observable<any> {
    return this.http.post(`${this.apiUrl}/game/start`, {})
      .pipe(tap(() => this.loadGameState()));
  }

  getValidMoves(y: number, x: number): Observable<[number, number][]> {
    return this.http.get<{ valid_moves: [number, number][] }>(`${this.apiUrl}/game/valid-moves?y=${y}&x=${x}`)
      .pipe(
        tap((response: { valid_moves: [number, number][] }) => this.validMoves$.next(response.valid_moves)),
        map((response: { valid_moves: [number, number][] }) => response.valid_moves)
      );
  }

  fetchValidMoves(y: number, x: number): Observable<[number, number][]> {
    return this.getValidMoves(y, x);
  }

  saveGame(filename: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/game/save`, { filename });
  }

  listSaves(): Observable<string[]> {
    return this.http.get<{ saves: string[] }>(`${this.apiUrl}/game/saves`)
      .pipe(tap(() => {}), map((response: { saves: string[] }) => response.saves || []));
  }

  loadGame(filename: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/game/load`, { filename })
      .pipe(tap(() => this.loadGameState()));
  }

  // Selection Management
  selectPiece(y: number, x: number, mode: 'move' | 'push' | 'place' | null = null): void {
    const state = this.getCurrentState();
    
    // Auto-detect mode if not specified
    if (mode === null) {
      if (state?.setup_mode) {
        mode = 'place';
      } else if (state && (state.moves_made >= 2 || !state.push_completed)) {
        mode = 'push';
      } else {
        mode = 'move';
      }
    }

    this.selectedPiece$.next([y, x]);
    this.actionMode$.next(mode);
    if (mode === 'move') {
      this.fetchValidMoves(y, x).subscribe();
    } else {
      this.validMoves$.next([]);
    }
  }

  clearSelection(): void {
    this.selectedPiece$.next(null);
    this.validMoves$.next([]);
    this.actionMode$.next(null);
  }

  getCurrentState(): GameState | null {
    return this.gameState$.value;
  }
}
