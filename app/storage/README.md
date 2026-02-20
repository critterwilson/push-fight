# Storage — Save / Load Utilities

Thin module for persisting and restoring game states to disk as JSON files.

## Files

| File | Purpose |
|------|---------|
| `game_storage.py` | `save_game()`, `load_game()`, `list_saves()`, `delete_save()` |

---

## API

All functions operate on the `saves/` directory at the project root.

```python
from app.storage.game_storage import save_game, load_game, list_saves, delete_save

# Save
path = save_game(game_state, "my_game")     # → "saves/my_game.json"

# Load
game_state = load_game("my_game")           # adds .json if missing

# List
names = list_saves()                        # ["game1", "game2", ...]

# Delete
deleted = delete_save("my_game")            # True if existed
```

All functions add `.json` automatically if the filename doesn't already end with it.

---

## Serialization Format

Save files are JSON produced by `GameState.to_dict()` / `GameState.from_dict()`. The format includes the full board grid, all piece positions, anchor position, turn counters, pieces-pushed-off counts, and win state.

See [app/engine/README.md](../engine/README.md) for the engine's serialization details.

---

## Notes

- The `saves/` directory is created automatically if it doesn't exist.
- In the Docker container, `saves/` is mounted as an `emptyDir` volume and is lost on pod restart. Replace with a PVC for persistence across restarts.
- The server's `SaveService` (`app/server/services/save_service.py`) delegates to this module for all save/load operations.
