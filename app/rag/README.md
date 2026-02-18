# RAG — Rules Referee

An LLM-backed referee that answers questions about the current game state and the rules of Push Fight. Uses **Retrieval-Augmented Generation (RAG)**: rules are chunked, embedded into a vector store, and retrieved at query time to ground the LLM's answers in the actual rulebook.

## Files

| File | Purpose |
|------|---------|
| `rag_engine.py` | `PushFightRAG` — ingestion, retrieval chain, LangChain pipeline |
| `ai_interface.py` | `AIInterface` singleton — non-blocking wrapper; runs queries in background threads |
| `state_formatter.py` | `format_game_state()` — converts a `GameState` into a human-readable string for the LLM prompt |

---

## Stack

| Component | Technology |
|-----------|-----------|
| LLM | Ollama (`llama3`) |
| Embeddings | Ollama (`nomic-embed-text`) |
| Vector store | ChromaDB |
| Orchestration | LangChain |
| Rules source | `assets/rules.md` |

---

## How It Works

### 1. Ingestion

`PushFightRAG._initialize_vector_store()` reads `assets/rules.md` and splits it by Markdown headers using LangChain's `MarkdownHeaderTextSplitter`. The resulting chunks are embedded with `nomic-embed-text` and stored in ChromaDB.

Two storage modes:
- **Remote ChromaDB** (production/K8s): set `CHROMA_HOST` and `CHROMA_PORT` env vars → connects to the ChromaDB service; ingests on first run if the collection is empty.
- **Local ChromaDB** (dev): stored at `./chroma_db`; created on first run, reloaded on subsequent runs.

### 2. Retrieval

At query time, the question is embedded and used to retrieve the 3 most relevant rule chunks from ChromaDB (`k=3`).

### 3. Generation

Retrieved chunks + formatted game state + user question are assembled into a LangChain `ChatPromptTemplate` and sent to `llama3` via Ollama. The system prompt instructs the LLM to:

- Answer only from the provided rules and game state
- Cite rule sections when rejecting illegal moves
- Format output in Markdown (headings, bullet lists, bold for key terms)

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

`format_game_state(game)` produces a compact text snapshot for the LLM prompt:

```
Current Player: white

Recent Moves (3 total):
  - {'type': 'move', 'player': 'white', ...}
  ...

Board Configuration:
[ASCII board representation]
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
