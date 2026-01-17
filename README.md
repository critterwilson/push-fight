# Push Fight - Rules of the Game

[cite_start]**Push Fight** is a game of skill and surprise[cite: 7]. [cite_start]Two players battle on a game board as the white team plays the brown team[cite: 7].

## The Goal
* [cite_start]The goal is for a player to push **ONE** of their opponent's game pieces off the board at either end[cite: 8].
* [cite_start]When one piece is off the board, the game is over[cite: 43].

---

## The Pieces
[cite_start]Each team has 5 game pieces[cite: 10]:
* [cite_start]**3 Square Pieces**: These have the power to **PUSH** one or more pieces one space[cite: 10, 12, 30].
* [cite_start]**2 Round Pieces**: These can move around the board but **cannot push**[cite: 10, 34].

---

## The Board Layout
* [cite_start]**Playable Spaces**: All pieces travel on empty spaces that are connected by sides that touch[cite: 11, 28].
* [cite_start]**Side Rails**: You cannot push or move a piece on or over a side railing[cite: 49].
* [cite_start]**End Zones (-1)**: Pieces are pushed off the board at either end to win[cite: 20, 42].
* **Centerline**: The board is divided by a centerline between rows 4 and 5. The white team starts on the north side (rows 0-4), and the brown team starts on the south side (rows 5-9).

---

## Initial Setup
Before the game begins, players place their pieces on the board:

* **Placement Rules**:
  * Each player must place exactly **3 square pieces** and **2 round pieces** (5 pieces total)
  * White team places pieces on rows 0-4 (north of the centerline)
  * Brown team places pieces on rows 5-9 (south of the centerline)
  * Pieces can be placed anywhere on your side of the centerline, as long as the space is playable (not a kill zone)
  * You cannot place pieces on the opponent's side or in kill zones

* **Starting the Game**: Once both players have placed all 5 pieces according to the rules, the game begins with the white team going first.



---

## How to Play
[cite_start]Players take turns, with the **white team going first**[cite: 24]. A single turn consists of two phases:

### 1. The Moves (Up to 2)
* [cite_start]You can start your turn by positioning **0, 1, or 2** of your pieces[cite: 24, 26, 29].
* [cite_start]Move a piece (round or square) and leave it; then you may move a second piece[cite: 27].
* [cite_start]You may travel as far as you want on connected empty spaces[cite: 28, 29].
* [cite_start]No diagonal moves are allowed[cite: 21].
* [cite_start]You cannot jump over other game pieces[cite: 50].

### 2. The Push (Mandatory)
* [cite_start]You **MUST** use one of your square pieces to push **ONE** space to complete your turn[cite: 30, 31, 51, 52].
* [cite_start]You can push white and/or brown pieces in any direction except diagonally[cite: 32].
* [cite_start]If several pieces are lined up in the direction of the push with no empty spaces between them, you push them all one space[cite: 33].
* [cite_start]If you cannot leave yourself a legal push, you lose[cite: 51].

---

## The Anchor Mechanic
[cite_start]Players share **one red anchor** piece to prevent repetitive moves[cite: 36, 41].

* [cite_start]After you push, place the anchor on the square piece that did the pushing[cite: 36].
* [cite_start]The anchored piece **cannot be pushed** during your opponent's next turn[cite: 37].
* [cite_start]If the anchored piece is in a line of pieces, none of them can be pushed if it would result in moving the anchored piece[cite: 39].
* [cite_start]Once the anchor is moved to a different piece, the previously anchored piece can be pushed again[cite: 40].



---

## Winning and Losing
* [cite_start]**Victory**: Trap your opponent so you can push one of their pieces off the board at either end[cite: 42].
* [cite_start]**Trapped**: You win if your opponent surrenders because they are trapped and cannot get out[cite: 45].
* [cite_start]**Draw**: If players get stuck for any reason, they can agree to a draw (which is very rare)[cite: 53, 54].

---
## Development

### Quick Start with Tmuxinator

If you have tmuxinator installed, start both backend and frontend with one command:

```bash
tmuxinator start push-fight-app
```

### Manual Setup

To run the game in development mode:

1. Start the Flask API server:
   ```bash
   uv run python -m app.main --web
   ```

2. In a separate terminal, start the Angular frontend:
   ```bash
   cd frontend
   npm install  # First time only
   npm start
   ```

The Angular dev server will proxy API requests to Flask automatically.

See [DEVELOPMENT.md](DEVELOPMENT.md) for more detailed development instructions.

---

[cite_start]*Copyright © 2018 Brettco, Inc. All Rights Reserved* [cite: 59]