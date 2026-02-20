# Benchmark — Ollama Model Evaluation

Tests Ollama models against game-state-specific questions to measure answer quality for the RAG referee system.

## Files

| File | Purpose |
|------|---------|
| `benchmark_models.py` | Benchmark runner — scenarios, questions, scoring, CLI |
| `dashboard.html` | Standalone HTML dashboard for visualizing results |
| `benchmark_results.json` | Latest benchmark output (auto-generated) |

---

## Quick Start

```bash
# Test a specific model (quick mode — 2 questions per scenario)
python benchmark/benchmark_models.py --models llama3 --quick

# Test all installed models
python benchmark/benchmark_models.py

# Pull missing models before testing
python benchmark/benchmark_models.py --pull

# Test only small/medium/large tiers
python benchmark/benchmark_models.py --small
python benchmark/benchmark_models.py --medium
python benchmark/benchmark_models.py --large
```

Results are saved to `benchmark/benchmark_results.json`. Open `benchmark/dashboard.html` in a browser to visualize them.

---

## Model Tiers

| Tier | Models |
|------|--------|
| Small | gemma3:1b, llama3.2:1b, qwen2.5:1.5b, phi4-mini |
| Medium | llama3.2:3b, gemma3:4b, mistral |
| Large | llama3, llama3.1:8b, gemma3:12b |

---

## Scenarios

The benchmark creates 6 distinct game states to test different aspects of rule knowledge:

| Scenario | Description |
|----------|-------------|
| `opening` | Standard opening position, white to move first |
| `mid_game_moved` | White has made 1 move, 1 remaining |
| `push_phase` | Both moves used, must push now |
| `anchor_blocking` | Black's turn with anchor blocking a key piece |
| `near_kill_zone` | Black's neck piece 1 square from elimination |
| `game_over` | Game ended, black wins |

Each scenario has 2-4 questions across categories: **state**, **legality**, **rules**, and **strategy** (18 total).

---

## Scoring

Each answer is scored on 4 dimensions, combined into a 0-100 composite:

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| Keyword relevance | 30% | Does the answer mention expected terms (piece names, rules)? |
| Factual correctness | 35% | For yes/no questions, did the model get the binary answer right? |
| Hallucination-free | 25% | Does the answer avoid terms from other games (chess, checkers, etc.)? |
| Conciseness | 10% | Is the answer in the sweet spot (30-300 words)? |

### Hallucination detection

The benchmark checks for terms that don't exist in Push Fight rules:
- Chess terms: pawn, rook, bishop, knight, king, queen
- Wrong mechanics: diagonal, capture, jump, promote
- Made-up terms: winged, leg piece

---

## Dashboard

`dashboard.html` is a standalone HTML file (no build step) that loads `benchmark_results.json` and displays:

- Model cards with composite scores
- Bar charts comparing dimensions across models
- Per-category performance breakdown
- Question explorer with click-to-compare answers across models
- CORRECT/WRONG/HALLUC badges per answer

Open it directly in a browser — it auto-loads `benchmark_results.json` from the same directory via `fetch()`, with a drag-and-drop fallback.

---

## CLI Flags

| Flag | Description |
|------|-------------|
| `--models MODEL [MODEL ...]` | Specific models to test |
| `--small` / `--medium` / `--large` | Test only one tier |
| `--quick` | 2 questions per scenario instead of all |
| `--pull` | Pull missing models from Ollama before testing |
| `--output PATH` | Custom output path (default: `benchmark/benchmark_results.json`) |
