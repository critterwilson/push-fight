# RAG — Rules Referee

An LLM-backed referee that answers questions about the current game state and the rules of Push Fight. Uses **Retrieval-Augmented Generation (RAG)**: rules are chunked, embedded into a vector store, and retrieved at query time to ground the LLM's answers in the actual rulebook.

## Files

| File | Purpose |
|------|---------|
| `rag_engine.py` | `PushFightRAG` — ingestion, retrieval chain, LangChain pipeline |
| `ai_interface.py` | `AIInterface` singleton — non-blocking wrapper; runs queries in background threads |
| `state_formatter.py` | `format_game_state()` — converts a `GameState` into a structured context string for the LLM prompt |

---

## Stack

| Component | Technology |
|-----------|-----------|
| LLM | Ollama (`llama3` default, configurable) |
| Embeddings | Ollama (`nomic-embed-text`) |
| Vector store | ChromaDB |
| Orchestration | LangChain |
| Rules source | `assets/rules.md` |

---

## How It Works

### 1. Ingestion

`PushFightRAG._initialize_vector_store()` reads `assets/rules.md` and splits it by Markdown headers using LangChain's `MarkdownHeaderTextSplitter`. The resulting chunks are embedded with `nomic-embed-text` and stored in ChromaDB.

Two storage modes:
- **Remote ChromaDB** (production/K8s): set `CHROMA_HOST` and `CHROMA_PORT` env vars -> connects to the ChromaDB service; ingests on first run if the collection is empty.
- **Local ChromaDB** (dev): stored at `./chroma_db`; created on first run, reloaded on subsequent runs.

### 2. Retrieval

At query time, the question is embedded and used to retrieve the **5 most relevant** rule chunks from ChromaDB (`k=5`).

### 3. Generation

Retrieved chunks + formatted game state + user question are assembled into a LangChain `ChatPromptTemplate` and sent to the LLM via Ollama.

**LLM configuration:**
- `temperature=0` — deterministic, factual answers (no creative hallucination)
- `num_predict=300` — hard output cap prevents runaway repetitive output

**System prompt** includes:
- Game basics (piece names, shapes, rules) baked directly into the prompt so the LLM always has ground truth
- Explicit instructions to use actual piece names (sleeve, lapel, belt, neck, joint) and never invent terms
- Conciseness constraint (under 100 words)
- For yes/no questions, start with "Yes" or "No" immediately

### 4. Delivery

The answer is returned as a string and broadcast over WebSocket as a `rag_answer` event by the server.

---

## AIInterface

`AIInterface` is a **singleton** that initializes the heavy RAG engine (`PushFightRAG`) in a background daemon thread so it doesn't block server startup.

```python
ai = AIInterface()          # returns the same instance every time
ai.ask_question(game, "Can I push a round piece?", callback)
```

`ask_question()` is non-blocking — it runs the LangChain chain in a background thread and invokes `callback(answer: str)` when done. The server bridges this to `asyncio` via `loop.call_soon_threadsafe()`.

---

## State Formatter

`format_game_state(game)` produces a structured text snapshot for the LLM prompt, including:

- **Phase and turn info** — current player, whether in move/push/setup/game_over phase, moves remaining
- **Anchor** — position, which piece it's on, reminder that opponent cannot move/push it
- **Piece inventory** — every piece per team with name, shape, and board coordinate (e.g. "sleeve (square) at A5")
- **Eliminations** — count of square/round pieces pushed off per team
- **Recent actions** — last 3 moves/pushes from the move log

Example output:
```
Current player: white. Phase: MOVE (1 move(s) remaining, or skip to push).
Anchor: on white's lapel at B6. Opponent cannot move or push this piece.
White pieces: sleeve (square) at A4, lapel (square) at B6, belt (square) at C5, neck (round) at D5, joint (round) at B4.
Black pieces: sleeve (square) at A6, lapel (square) at B7, belt (square) at C6, neck (round) at D6, joint (round) at B7.
Eliminations: none.
Recent actions: white moved (4, 0)->(3, 0).
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama service URL |
| `CHROMA_HOST` | _(unset)_ | ChromaDB hostname; if unset, uses local `./chroma_db` |
| `CHROMA_PORT` | `8000` | ChromaDB port (used with `CHROMA_HOST`) |

---

## Local Setup

Ollama must be running with the required models pulled:

```bash
ollama pull llama3
ollama pull nomic-embed-text
```

The vector store is built automatically on first run from `assets/rules.md`.

---

## Benchmarking

The `benchmark/` directory at the project root tests LLM answer quality. See [benchmark/README.md](../../benchmark/README.md).
