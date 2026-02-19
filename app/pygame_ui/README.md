# PyGame UI — Legacy Local Interface

A standalone desktop UI built with PyGame. Predates the React/FastAPI web app and is no longer the primary interface, but remains useful for quick local testing without a browser.

## Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point — main game loop, event handling, button layout |
| `game_view.py` | `GameView` — wraps `GameState`, coordinates game-mode switching and AI turns |
| `board_renderer.py` | `BoardRenderer` — draws the 10×4 board, pieces, highlights, and selection to a PyGame surface |
| `input_handler.py` | `InputHandler` — translates mouse clicks and keyboard events into move/push actions |
| `ui_components.py` | `Button`, `StatusPanel` — reusable UI widgets |
| `chat_overlay.py` | `ChatOverlay` — full-screen RAG referee panel with text input and answer display |

---

## Running

```bash
uv run python -m app.pygame_ui.main
```

Requires PyGame to be installed (`uv sync --dev` includes it).

---

## Features

- **PvP and PvCPU modes** — switch at any time via mode buttons
- **AI model selection** — dialog lists all `.zip` files in `models/`; if none found, falls back to a filename text input
- **Push direction pad** — on-screen arrow buttons appear during the push phase when a square piece is selected
- **RAG Referee** — "Ask Referee" button opens the `ChatOverlay`; questions are submitted to `AIInterface` (same singleton as the web server) and answers are displayed when ready
- **Save / Load** — text-input dialogs write/read from the `saves/` directory via `GameState.save_to_file()` / `load_from_file()`
- **Skip Moves** — button appears during the move phase to go straight to pushing

---

## AI Turn Handling

AI moves run on a timer (`AI_MOVE_DELAY = 600 ms`) rather than blocking the main loop. `GameView.execute_ai_turn()` is called each frame while it's the AI's turn, advancing the game one action at a time.

---

## Limitations

- **Local only** — no networking; runs the engine directly in-process
- **No voice control** — voice commands are a web-only feature (Web Speech API)
- **No setup-phase UI** — uses the default starting position (`GameState.create_initial_game()`)
- Not tested against the full test suite; consider the web interface canonical for correctness
