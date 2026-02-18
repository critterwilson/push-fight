# Push Fight: BJJ Edition — Official Rules

## 1. Game Overview and Objective

### What is Push Fight?
Push Fight is a tactical two-player board game played on a 10×4 grid. Each player controls five BJJ-themed pieces. The goal is to push an opponent's piece off an open end of the board into a Kill Zone, or to trap your opponent so they cannot make a legal push.

This digital edition uses Brazilian Jiu-Jitsu grip and submission names for the pieces, enabling voice commands and thematic play.

### How to Win
You win instantly when any of these conditions are met:
- You push one of your opponent's **round pieces** (Choke or Lock) off the board into a Kill Zone.
- You push **two of your opponent's square pieces** (any two of Sleeve, Lapel, Belt) off the board.
- Your opponent begins their turn with **no legal push available** — they are trapped and lose immediately.

### How to Lose
You lose instantly when any of these conditions are met:
- One of your **own round pieces** (Choke or Lock) is pushed off the board.
- **Two of your own square pieces** (Sleeve, Lapel, Belt) are pushed off the board.
- You initiate a push that sends **your own piece** off the board — even if an opponent's piece also leaves.
- You begin your turn with **no legal push available** (every possible push is illegal).


## 2. Pieces and Their Roles

### Square Pieces — BJJ Grips (Can Move and Push)
Each player has **three square pieces**. Square pieces are the only pieces that can initiate a push. They are named after BJJ grips:

| Piece Name | Grip Type | Can Push | Defeat Condition |
|------------|-----------|----------|-----------------|
| **Sleeve** | Sleeve grip — controls distance | Yes | Losing 2 square pieces total |
| **Lapel**  | Lapel grip — dominant control   | Yes | Losing 2 square pieces total |
| **Belt**   | Belt grip — body clinch          | Yes | Losing 2 square pieces total |

Losing any **two** square pieces (in any combination of Sleeve, Lapel, Belt) results in immediate defeat.

### Round Pieces — BJJ Submissions (Can Move, Cannot Push)
Each player has **two round pieces**. Round pieces can move but cannot initiate a push. They are named after BJJ submissions:

| Piece Name | Submission Type | Can Push | Defeat Condition |
|------------|----------------|----------|-----------------|
| **Choke** | Strangulation submission | No | Losing just 1 round piece |
| **Lock**  | Joint lock submission    | No | Losing just 1 round piece |

Round pieces are high-value targets: losing **even one** round piece (Choke or Lock) is an immediate defeat. Protect them carefully.

### Piece Summary: Point Values
- Round pieces (Choke, Lock): worth **1 life each** — lose one and you lose the game.
- Square pieces (Sleeve, Lapel, Belt): worth **½ life each** — lose two and you lose the game.


## 3. The Board Layout

### Board Dimensions and Coordinate System
The board is **10 rows × 4 columns**. Coordinates are used for movement commands and voice control.

- **Columns**: A (leftmost) → B → C → D (rightmost)
- **Rows**: 1 (top, White's back edge) → 10 (bottom, Black's back edge)
- **Coordinate format**: column letter + row number. Examples: A1, B4, C7, D10.
- White occupies the **north half** (rows 1–5). Black occupies the **south half** (rows 6–10).

Coordinate examples for voice commands:
- B4 = column B, row 4 (row index 3, col index 1)
- C6 = column C, row 6 (row index 5, col index 2)

### Kill Zones — Where Pieces Are Eliminated
Kill zones are the open ends of the board. Any piece pushed into a Kill Zone is **immediately removed from play**. If the removed piece belongs to you, you lose.

Kill zone cell locations:
- All of **Row 1**: A1, B1, C1, D1 — White's back edge (north kill zone)
- All of **Row 10**: A10, B10, C10, D10 — Black's back edge (south kill zone)
- Irregular corners: **A2, D2** (row 2 corners), **D3** (row 3 right corner)
- Irregular corners: **A8** (row 8 left corner), **A9, D9** (row 9 corners)

A piece that enters a Kill Zone cannot be saved — removal is instant and permanent.

### Side Rails — Impassable Walls
The outer edges of the board (the long sides) are **Side Rails** — solid walls. Pieces cannot be pushed through or into Side Rails.

- If a push would cause any piece in the push chain to collide with a Side Rail, the **entire push is illegal** and cannot be performed.
- Side Rails are different from Kill Zones: Kill Zones eliminate pieces; Side Rails block pushes entirely.


## 4. Game Setup and Starting Positions

### Initial Piece Placement (Standard Layout)
In this digital version, pieces start in a fixed layout:

**White pieces (rows 1–5):**
- Sleeve at A5, Lapel at B5, Belt at C5, Choke at D5, Lock at B4.

**Black pieces (rows 6–10):**
- Sleeve at A6, Lapel at B6, Belt at C6, Choke at D6, Lock at B7.

### First Turn and Anchor Start
White always moves first. The Anchor is **not placed** until White completes the very first push of the game.


## 5. Turn Structure

### Overview of Every Turn
Every turn consists of exactly two phases, always in this order:
1. **Move Phase** (optional): Move 0, 1, or 2 pieces orthogonally.
2. **Push Phase** (mandatory): Perform exactly 1 push using a square piece.

You cannot skip the push phase. Completing a push ends your turn and places the Anchor.

### Move Phase — Full Rules
During the move phase:
- You may move **0, 1, or 2 pieces** per turn (moving is optional).
- A single move = sliding one piece **any number of empty squares** in one orthogonal direction (up, down, left, or right).
- You **cannot move diagonally**.
- You **cannot move through or jump over** any other piece (yours or your opponent's).
- You may move **the same piece twice**, or two different pieces once each.
- You **cannot move the anchored piece** (the piece currently marked by the Anchor token).
- Use the "Skip" button or say "skip" to skip your remaining moves and go directly to the push phase.

### Push Phase — Full Rules
After your move phase (even with 0 moves), you must push:
- Select one of your **square pieces** (Sleeve, Lapel, or Belt) to push with.
- Push it one square into an **adjacent occupied cell** in one orthogonal direction.
- All pieces in a continuous chain behind the target piece shift **one square** in the push direction.
- After the push, the **Anchor is placed** on the piece you just pushed with.
- If no legal push is available at the start of your turn, you **lose immediately**.


## 6. Pushing Rules and Restrictions

### How a Push Works (Mechanics)
A push is performed by a square piece (Sleeve, Lapel, or Belt). The pushing piece moves into an adjacent occupied cell, and all pieces in the resulting chain are shifted one square.

**Example**: White's Sleeve is at B5. White pushes Sleeve down (toward row 10). Black's Lapel is at B6, and B7 is empty. Result: Sleeve moves to B6, Black's Lapel moves to B7.

**Chain example**: White's Belt at C5 pushes right. Black's Choke is at D5. D5 is adjacent to the right edge — pushing Choke off the board would enter a Kill Zone, eliminating it. Check whether that is a win or a loss depending on which team's piece it is.

### Illegal Push Conditions — When a Push Cannot Be Performed
A push is **illegal** (forbidden) if any of these apply:
- There is **no piece adjacent** to the pushing piece in the chosen direction (nothing to push into).
- Any piece in the push chain would be moved **into a Side Rail** (left or right wall).
- The piece being pushed, or **any piece in the chain**, is the **anchored piece** (has the Anchor token).

### Pushes That Cause Elimination (Kill Zone Pushes)
A push that sends a piece off the board into a Kill Zone is **legal**. The piece is removed immediately.
- Pushing an **opponent's piece** off = potential win for you.
- Pushing your **own piece** off = immediate loss for you, even if an opponent's piece also leaves.
- Only square pieces can initiate pushes — round pieces (Choke, Lock) cannot push.

### Push Direction
Pushes are orthogonal only: **up, down, left, right**. Diagonal pushes are not allowed.


## 7. The Anchor

### What is the Anchor?
The Anchor is a token placed on the last piece to perform a push. It prevents repetitive back-and-forth play by restricting what the opponent can do on their next turn.

### When is the Anchor Placed?
The Anchor is placed **at the end of every turn**, on the square piece that just pushed. It stays on that piece until the next push is performed.

### Anchor Effects on the Opponent
During the opponent's very next turn, the anchored piece has these restrictions:
1. The opponent **cannot move the anchored piece** during their move phase.
2. The opponent **cannot push the anchored piece** — it acts as an immovable wall.
3. The opponent **cannot push any chain that includes the anchored piece** — even if the anchored piece is not the first in the chain.

The anchor is removed (transferred to the new pushing piece) when the current player completes their push.

### Anchor Does Not Affect the Current Player
The player who just placed the Anchor is not restricted by it — only their opponent is restricted on the next turn.

### Anchor and Losing by Trap
If the Anchor (combined with Side Rails and board position) means the opponent has **no legal push** when their turn begins, that opponent **loses immediately**. This is a valid and powerful win condition.


## 8. Complete Win and Loss Reference

### Win Conditions (any one of these ends the game immediately)
- Push opponent's **Choke** off the board → You win.
- Push opponent's **Lock** off the board → You win.
- Push opponent's second **square piece** (2nd of Sleeve/Lapel/Belt) off the board → You win.
- Opponent has **no legal push** at the start of their turn → You win.

### Loss Conditions (any one of these ends the game immediately)
- Your **Choke** is pushed off the board → You lose.
- Your **Lock** is pushed off the board → You lose.
- Your second **square piece** (2nd of Sleeve/Lapel/Belt) is pushed off the board → You lose.
- You **initiate a push** that sends your own piece off the board → You lose.
- You have **no legal push** at the start of your turn → You lose.

### Piece Values Reference Table
| Piece  | Shape  | Can Push | Pieces Lost to Lose |
|--------|--------|----------|---------------------|
| Sleeve | Square | Yes      | Need 2 squares lost |
| Lapel  | Square | Yes      | Need 2 squares lost |
| Belt   | Square | Yes      | Need 2 squares lost |
| Choke  | Round  | No       | Need only 1 lost    |
| Lock   | Round  | No       | Need only 1 lost    |


## 9. Voice Control Commands

### How Voice Control Works
This digital version supports voice commands. Speak clearly using the piece name followed by the action. Commands are processed for the **current player's pieces only**.

### Voice Move Commands
Format: `[piece name] to [column][row]`

Examples:
- **"Sleeve to B4"** — moves your Sleeve piece to column B, row 4.
- **"Choke to C6"** — moves your Choke piece to column C, row 6.
- **"Lock to A3"** — moves your Lock piece to column A, row 3.

### Voice Push Commands
Format: `[piece name] push [direction]`

Only square pieces (Sleeve, Lapel, Belt) can push.

Examples:
- **"Lapel push down"** — pushes with Lapel toward row 10.
- **"Belt push up"** — pushes with Belt toward row 1.
- **"Sleeve push left"** — pushes with Sleeve toward column A.
- **"Sleeve push right"** — pushes with Sleeve toward column D.

### Voice Skip Command
- **"skip"** or **"skip moves"** — ends your move phase and proceeds to the push phase.

### Voice Command Constraints
- You cannot issue commands for your opponent's pieces.
- Push commands only work for Sleeve, Lapel, and Belt (square pieces only).
- The coordinate system uses letters A–D for columns and numbers 1–10 for rows.


## 10. Frequently Asked Questions

### Can Choke or Lock push another piece?
No. Section 6: Only square pieces (Sleeve, Lapel, Belt) can initiate a push. Round pieces (Choke, Lock) are passive — they can only move.

### Can I skip moving and go straight to pushing?
Yes. Section 5: Moving is optional. You can move 0, 1, or 2 times. Click the "Skip" button or say "skip" to go directly to the push phase.

### What happens if I push my own piece off the board?
Section 8: You lose immediately. Pushing your own piece off a Kill Zone end counts as a loss for you, regardless of whether an opponent's piece also left.

### Can I push the piece with the Anchor on it?
No. Section 7: The anchored piece cannot be moved or pushed, and it blocks any push chain that includes it. It acts as a fixed wall for your opponent on their next turn.

### Can two pieces be eliminated in one push?
Yes. If a push chain reaches a Kill Zone end, multiple pieces can be pushed off in a single action. If any of those pieces are yours, you lose.

### What if the board is arranged so I cannot push at all?
Section 1: If you begin your turn and have no legal push available (every square piece is blocked by Side Rails, the Anchor, or no adjacent pieces), you lose the game immediately.

### Is there a difference between losing Choke vs. losing Sleeve?
Yes. Section 2: Losing one round piece (Choke or Lock) = immediate defeat. Losing one square piece (Sleeve, Lapel, or Belt) does not end the game — you must lose two square pieces to lose.

### What is the difference between a Kill Zone and a Side Rail?
Section 3: Kill Zones are the open ends of the board (rows 1 and 10, plus the irregular corner cells). Pieces pushed into Kill Zones are eliminated. Side Rails are the impassable walls on the long sides — pushing a chain into a Side Rail makes the push illegal; no piece moves and nothing is eliminated.

### Can I use a round piece to block a push?
Yes. A round piece in a push chain will be pushed along with everything else. If a push chain includes both your piece and an opponent's piece, all of them move. Be aware that if your piece would leave the board, you lose.

### How does the Anchor prevent repetitive play?
Section 7: After every push, the Anchor is placed on the piece that pushed. The opponent cannot move or push that piece on their next turn. This prevents the same push from being reversed immediately, forcing both players to think ahead.

### Can I win by pushing the opponent's Sleeve but not Lapel or Belt?
Section 8: Pushing one square piece (Sleeve, Lapel, or Belt) does not win the game. You need to eliminate any two square pieces in total. However, if you push the opponent's Choke or Lock (round pieces), you win immediately with just one elimination.
