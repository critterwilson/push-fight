#!/usr/bin/env python3
"""
Benchmark Ollama models for the Push Fight RAG referee use case.

Tests multiple models against a suite of game-state-specific questions,
measuring response time and answer quality.

Usage:
    python benchmark_models.py                     # run all models
    python benchmark_models.py --models llama3 gemma3:1b  # specific models
    python benchmark_models.py --pull               # pull missing models first
    python benchmark_models.py --quick              # fewer questions per scenario
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from textwrap import indent

# Ensure project root is on the path (script lives in benchmark/ subfolder)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from app.engine.game_state import GameState
from app.engine.board import PushFightBoard
from app.engine.pieces import Piece
from app.rag.rag_engine import PushFightRAG
from app.rag.state_formatter import format_game_state


# ---------------------------------------------------------------------------
# Models to benchmark (small → large)
# ---------------------------------------------------------------------------

SMALL_MODELS = [
    "gemma3:1b",
    "llama3.2:1b",
    "qwen2.5:1.5b",
    "phi4-mini",
]

MEDIUM_MODELS = [
    "llama3.2:3b",
    "gemma3:4b",
    "mistral",
]

LARGE_MODELS = [
    "llama3",
    "llama3.1:8b",
    "gemma3:12b",
]

ALL_MODELS = SMALL_MODELS + MEDIUM_MODELS + LARGE_MODELS


# ---------------------------------------------------------------------------
# Game scenarios — each creates a specific GameState for targeted questions
# ---------------------------------------------------------------------------

def scenario_opening() -> GameState:
    """Standard opening position — white to move first."""
    return GameState.create_initial_game()


def scenario_mid_game_white_moved() -> GameState:
    """Mid-game: white has made 1 move, about to move or push."""
    game = GameState.create_initial_game()
    game.perform_move((4, 0), (3, 0))  # sleeve slides up
    return game


def scenario_push_phase() -> GameState:
    """White has used both moves, must now push."""
    game = GameState.create_initial_game()
    game.perform_move((4, 0), (2, 0))  # sleeve slides up 2
    game.perform_move((3, 1), (3, 0))  # joint slides left
    return game


def scenario_anchor_blocking() -> GameState:
    """Black's turn with white's anchor blocking a key piece."""
    game = GameState.create_initial_game()
    # White pushes lapel down — pushes into black's sleeve
    game.perform_push(4, 1, (1, 0))  # lapel pushes down
    game.switch_turn()  # now it's black's turn, anchor on (5,1)
    return game


def scenario_near_kill_zone() -> GameState:
    """A black piece is 1 square from the north kill zone — high tension."""
    board = PushFightBoard()
    # White pieces — set up for a potential kill push
    board.pieces[2][1] = Piece('white', 'square', name='sleeve')
    board.pieces[3][0] = Piece('white', 'square', name='lapel')
    board.pieces[4][2] = Piece('white', 'square', name='belt')
    board.pieces[4][3] = Piece('white', 'round', name='neck')
    board.pieces[3][2] = Piece('white', 'round', name='joint')
    # Black pieces — neck is dangerously close to kill zone at row 1
    board.pieces[1][1] = Piece('black', 'round', name='neck')  # 1 push from death!
    board.pieces[5][0] = Piece('black', 'square', name='sleeve')
    board.pieces[5][1] = Piece('black', 'square', name='lapel')
    board.pieces[6][2] = Piece('black', 'square', name='belt')
    board.pieces[6][1] = Piece('black', 'round', name='joint')
    game = GameState(board)
    return game


def scenario_game_over() -> GameState:
    """Game is over — black wins."""
    game = GameState.create_initial_game()
    game.game_over = True
    game.winner = 'black'
    return game


# ---------------------------------------------------------------------------
# Test questions — each tied to a scenario with expected answer keywords
# ---------------------------------------------------------------------------

@dataclass
class Question:
    text: str
    category: str  # rules, state, strategy, legality
    expected_keywords: list[str] = field(default_factory=list)
    description: str = ""
    expected_answer: str | None = None  # "yes" or "no" for binary questions
    banned_terms: list[str] = field(default_factory=list)  # hallucination markers


# Hallucination markers — terms that don't exist in Push Fight rules.
# If the model uses these, it's inventing rules from other games.
COMMON_HALLUCINATIONS = [
    "pawn", "rook", "bishop", "knight", "king", "queen",  # chess
    "checker", "jump", "capture",  # checkers
    "dice", "roll",  # board games
    "promote", "promotion",  # chess
    "winged", "leg piece",  # made-up Push Fight terms
    "three spaces", "3 spaces",  # wrong move distance
    "diagonal",  # Push Fight is orthogonal-only
]

SCENARIOS: dict[str, dict] = {
    "opening": {
        "builder": scenario_opening,
        "description": "Standard opening — white to move first",
        "questions": [
            Question(
                text="What pieces can I move right now?",
                category="state",
                expected_keywords=["white", "sleeve", "lapel", "belt", "neck", "joint"],
                description="Should list all white pieces as movable",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
            Question(
                text="Can I push with my neck piece?",
                category="legality",
                expected_keywords=["no", "round", "square", "cannot push"],
                expected_answer="no",
                description="Round pieces cannot push — should say no",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
            Question(
                text="What is the difference between square and round pieces?",
                category="rules",
                expected_keywords=["square", "push", "round", "cannot", "move"],
                description="Should explain push capability difference",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
            Question(
                text="How many pieces do I need to push off to win?",
                category="rules",
                expected_keywords=["two", "square", "one", "round"],
                description="Should explain 2 squares or 1 round",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
        ],
    },
    "mid_game_moved": {
        "builder": scenario_mid_game_white_moved,
        "description": "White moved sleeve to (3,0) — 1 move used",
        "questions": [
            Question(
                text="How many moves do I have left this turn?",
                category="state",
                expected_keywords=["one", "1"],
                description="Should say 1 move remaining",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
            Question(
                text="Can I skip my remaining moves and push now?",
                category="legality",
                expected_keywords=["yes", "skip", "push"],
                expected_answer="yes",
                description="Should confirm skipping is allowed",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
            Question(
                text="Can I move the same piece I already moved?",
                category="rules",
                expected_keywords=["yes", "same piece", "twice"],
                expected_answer="yes",
                description="Rules allow moving same piece twice",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
        ],
    },
    "push_phase": {
        "builder": scenario_push_phase,
        "description": "White used both moves — must push now",
        "questions": [
            Question(
                text="Can I move another piece?",
                category="legality",
                expected_keywords=["no", "cannot", "push", "two moves", "already"],
                expected_answer="no",
                description="Should say no — both moves used, must push",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
            Question(
                text="Which pieces can I use to push?",
                category="state",
                expected_keywords=["square", "sleeve", "lapel", "belt"],
                description="Should list only square pieces",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
            Question(
                text="What happens after I push?",
                category="rules",
                expected_keywords=["anchor", "turn", "opponent"],
                description="Should explain anchor placement and turn end",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
        ],
    },
    "anchor_blocking": {
        "builder": scenario_anchor_blocking,
        "description": "Black's turn — white anchor at (5,1) blocks that piece",
        "questions": [
            Question(
                text="Why can't I push the piece at row 5, column B?",
                category="legality",
                expected_keywords=["anchor", "cannot", "push", "block"],
                description="Should explain anchor prevents moving/pushing that piece",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
            Question(
                text="What is the anchor and how does it affect me?",
                category="rules",
                expected_keywords=["anchor", "previous", "push", "cannot move", "cannot push"],
                description="Should explain anchor mechanics",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
            Question(
                text="Can I move the anchored piece to a different position?",
                category="legality",
                expected_keywords=["no", "cannot", "move", "anchor"],
                expected_answer="no",
                description="Anchored piece cannot be moved",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
        ],
    },
    "near_kill_zone": {
        "builder": scenario_near_kill_zone,
        "description": "Black's neck at row 1 col B — 1 push from elimination",
        "questions": [
            Question(
                text="Is black's neck piece in danger?",
                category="strategy",
                expected_keywords=["yes", "kill zone", "danger", "push", "row 1"],
                expected_answer="yes",
                description="Should identify the imminent threat",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
            Question(
                text="If I push my sleeve piece upward, what happens?",
                category="strategy",
                expected_keywords=["push", "neck", "kill zone", "off", "win"],
                description="Should explain the push would eliminate black's neck",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
            Question(
                text="What happens if a round piece is pushed off the board?",
                category="rules",
                expected_keywords=["lose", "immediately", "round", "one"],
                description="Losing 1 round piece = immediate loss",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
        ],
    },
    "game_over": {
        "builder": scenario_game_over,
        "description": "Game is over — black wins",
        "questions": [
            Question(
                text="Who won the game?",
                category="state",
                expected_keywords=["black", "win", "won"],
                description="Should say black won",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
            Question(
                text="Can I still make a move?",
                category="legality",
                expected_keywords=["no", "over", "ended"],
                expected_answer="no",
                description="Game is over — no more actions",
                banned_terms=COMMON_HALLUCINATIONS,
            ),
        ],
    },
}


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

@dataclass
class Result:
    model: str
    scenario: str
    question: str
    category: str
    answer: str
    elapsed_sec: float
    # Keyword coverage (0.0–1.0)
    keywords_found: list[str]
    keywords_missed: list[str]
    keyword_score: float
    # Factual correctness — did it get yes/no right? (True/False/None if N/A)
    factual_correct: bool | None
    # Hallucination detection — banned terms found in response
    hallucinations_found: list[str]
    hallucination_score: float  # 1.0 = clean, 0.0 = lots of hallucinations
    # Answer quality
    word_count: int
    # Composite score (0–100)
    composite_score: float


def check_keywords(answer: str, expected: list[str]) -> tuple[list[str], list[str], float]:
    """Check which expected keywords appear in the answer (case-insensitive)."""
    answer_lower = answer.lower()
    found = [kw for kw in expected if kw.lower() in answer_lower]
    missed = [kw for kw in expected if kw.lower() not in answer_lower]
    score = len(found) / len(expected) if expected else 1.0
    return found, missed, score


def check_factual(answer: str, expected_answer: str | None) -> bool | None:
    """For yes/no questions, check if the model got the binary answer right.

    Looks at the first substantive sentence to determine the model's stance.
    Returns True (correct), False (wrong), or None (not a yes/no question).
    """
    if expected_answer is None:
        return None

    answer_lower = answer.lower().strip()
    # Check the opening of the answer for the stance
    # Many models start with "**Yes**" or "**No**" or "Yes," etc.
    first_chunk = answer_lower[:200]

    # Strip markdown bold/italic
    first_chunk = first_chunk.replace("*", "").replace("#", "").strip()

    says_yes = False
    says_no = False

    # Check for strong yes/no indicators at the start
    for yes_phrase in ["yes", "you can", "absolutely", "correct", "indeed"]:
        if first_chunk.startswith(yes_phrase) or f"\n{yes_phrase}" in first_chunk[:80]:
            says_yes = True
            break

    for no_phrase in ["no", "you cannot", "you can't", "unfortunately", "illegal", "not allowed"]:
        if first_chunk.startswith(no_phrase) or f"\n{no_phrase}" in first_chunk[:80]:
            says_no = True
            break

    if expected_answer == "yes":
        if says_yes:
            return True
        if says_no:
            return False
        return None  # ambiguous
    elif expected_answer == "no":
        if says_no:
            return True
        if says_yes:
            return False
        return None  # ambiguous
    return None


def check_hallucinations(answer: str, banned_terms: list[str]) -> tuple[list[str], float]:
    """Detect hallucinated terms from other games.

    Returns (list of found banned terms, score 1.0=clean to 0.0=bad).
    """
    if not banned_terms:
        return [], 1.0
    answer_lower = answer.lower()
    found = [term for term in banned_terms if term.lower() in answer_lower]
    # Score: penalize heavily for hallucinations
    score = max(0.0, 1.0 - (len(found) * 0.25))
    return found, score


def compute_composite(keyword_score: float, factual_correct: bool | None,
                      hallucination_score: float, word_count: int) -> float:
    """Compute a 0–100 composite score from all dimensions.

    Weights:
        - Keyword relevance: 30%
        - Factual correctness: 35% (if applicable, else redistribute to keywords)
        - Hallucination-free: 25%
        - Conciseness: 10% (sweet spot: 50–300 words)
    """
    # Conciseness: penalize very short (<30 words) or very long (>500 words)
    if word_count < 30:
        conciseness = word_count / 30
    elif word_count <= 300:
        conciseness = 1.0
    elif word_count <= 500:
        conciseness = 1.0 - (word_count - 300) / 400
    else:
        conciseness = 0.5

    if factual_correct is not None:
        factual_score = 1.0 if factual_correct else 0.0
        composite = (
            keyword_score * 30
            + factual_score * 35
            + hallucination_score * 25
            + conciseness * 10
        )
    else:
        # No binary answer — redistribute factual weight to keywords
        composite = (
            keyword_score * 55
            + hallucination_score * 35
            + conciseness * 10
        )

    return round(composite, 1)


def get_installed_models() -> set[str]:
    """Return set of currently installed Ollama model names.

    Includes both the full tag (e.g. 'llama3:latest') and the short name
    (e.g. 'llama3') so that either form matches.
    """
    try:
        out = subprocess.check_output(["ollama", "list"], text=True, stderr=subprocess.DEVNULL)
        models = set()
        for line in out.strip().split("\n")[1:]:  # skip header
            if line.strip():
                full_name = line.split()[0]
                models.add(full_name)
                # Also add the short name without :latest tag
                if ":" in full_name:
                    short_name = full_name.rsplit(":", 1)[0]
                    models.add(short_name)
        return models
    except Exception:
        return set()


def pull_model(model: str) -> bool:
    """Pull an Ollama model. Returns True on success."""
    print(f"  Pulling {model}...")
    try:
        subprocess.check_call(["ollama", "pull", model], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"  Failed to pull {model}: {e}")
        return False


def run_benchmark(models: list[str], quick: bool = False) -> list[Result]:
    """Run all scenarios and questions against each model."""
    results: list[Result] = []

    # Build scenarios and questions
    scenarios_to_run = {}
    for name, cfg in SCENARIOS.items():
        game = cfg["builder"]()
        context = format_game_state(game)
        questions = cfg["questions"]
        if quick:
            questions = questions[:2]  # first 2 per scenario in quick mode
        scenarios_to_run[name] = {
            "description": cfg["description"],
            "context": context,
            "questions": questions,
        }

    total_questions = sum(len(s["questions"]) for s in scenarios_to_run.values())

    # Shared vector store — only the embedding model matters, not the LLM
    print("\n  Initializing shared vector store (nomic-embed-text)...")
    base_rag = PushFightRAG(rules_path="assets/rules.md", model_name=models[0])
    shared_retriever = base_rag.retriever
    shared_vector_store = base_rag.vector_store

    for model_idx, model in enumerate(models):
        print(f"\n{'='*70}")
        print(f"  MODEL {model_idx+1}/{len(models)}: {model}")
        print(f"  {total_questions} questions across {len(scenarios_to_run)} scenarios")
        print(f"{'='*70}")

        # Build a RAG chain for this model, reusing the shared vector store
        try:
            rag = PushFightRAG.__new__(PushFightRAG)
            rag.model_name = model
            rag.rules_path = "assets/rules.md"
            rag.vector_store = shared_vector_store
            rag.retriever = shared_retriever
            rag._build_chain()
        except Exception as e:
            print(f"  ERROR: Failed to initialize {model}: {e}")
            continue

        q_num = 0
        for scenario_name, scenario_data in scenarios_to_run.items():
            print(f"\n  --- {scenario_name}: {scenario_data['description']} ---")
            context = scenario_data["context"]

            for q in scenario_data["questions"]:
                q_num += 1
                print(f"  [{q_num}/{total_questions}] ({q.category}) {q.text}")

                start = time.time()
                try:
                    answer = rag.ask(q.text, context)
                except Exception as e:
                    answer = f"[ERROR] {e}"
                elapsed = time.time() - start

                found, missed, kw_score = check_keywords(answer, q.expected_keywords)
                factual = check_factual(answer, q.expected_answer)
                hallucinations, hall_score = check_hallucinations(answer, q.banned_terms)
                wc = len(answer.split())
                composite = compute_composite(kw_score, factual, hall_score, wc)

                results.append(Result(
                    model=model,
                    scenario=scenario_name,
                    question=q.text,
                    category=q.category,
                    answer=answer,
                    elapsed_sec=elapsed,
                    keywords_found=found,
                    keywords_missed=missed,
                    keyword_score=kw_score,
                    factual_correct=factual,
                    hallucinations_found=hallucinations,
                    hallucination_score=hall_score,
                    word_count=wc,
                    composite_score=composite,
                ))

                # Status line
                parts = [f"{elapsed:.1f}s"]
                parts.append(f"kw {len(found)}/{len(found)+len(missed)}")
                if factual is not None:
                    parts.append("CORRECT" if factual else "WRONG")
                if hallucinations:
                    parts.append(f"halluc: {hallucinations[:2]}")
                parts.append(f"score: {composite:.0f}/100")
                print(f"         {' | '.join(parts)}")

    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def print_summary(results: list[Result]):
    """Print a summary comparison table."""
    if not results:
        print("\nNo results to summarize.")
        return

    # Group by model (preserve order)
    models = []
    seen = set()
    for r in results:
        if r.model not in seen:
            models.append(r.model)
            seen.add(r.model)

    print(f"\n{'='*78}")
    print("  SUMMARY")
    print(f"{'='*78}")

    # Per-model overview
    header = f"  {'Model':<20} {'Time':>6} {'Score':>6} {'Keywords':>9} {'Factual':>8} {'Halluc':>7}"
    print(header)
    print(f"  {'-'*20} {'-'*6} {'-'*6} {'-'*9} {'-'*8} {'-'*7}")

    for model in models:
        mr = [r for r in results if r.model == model]
        avg_time = sum(r.elapsed_sec for r in mr) / len(mr)
        avg_comp = sum(r.composite_score for r in mr) / len(mr)
        avg_kw = sum(r.keyword_score for r in mr) / len(mr)

        factual_qs = [r for r in mr if r.factual_correct is not None]
        factual_pct = (sum(1 for r in factual_qs if r.factual_correct) / len(factual_qs) * 100) if factual_qs else -1

        avg_hall = sum(r.hallucination_score for r in mr) / len(mr)

        factual_str = f"{factual_pct:.0f}%" if factual_pct >= 0 else "n/a"
        print(f"  {model:<20} {avg_time:>5.1f}s {avg_comp:>5.0f}/100 {avg_kw:>8.0%} {factual_str:>8} {avg_hall:>6.0%}")

    # Per-category composite scores
    categories = sorted(set(r.category for r in results))
    print(f"\n  --- Composite score by category ---")
    header = f"  {'Model':<20}" + "".join(f" {cat:>10}" for cat in categories)
    print(header)
    print(f"  {'-'*20}" + "".join(f" {'-'*10}" for _ in categories))
    for model in models:
        row = f"  {model:<20}"
        for cat in categories:
            cat_results = [r for r in results if r.model == model and r.category == cat]
            if cat_results:
                avg = sum(r.composite_score for r in cat_results) / len(cat_results)
                row += f" {avg:>9.0f}"
            else:
                row += f" {'n/a':>10}"
        print(row)


def save_detailed_results(results: list[Result], output_path: str):
    """Save full results with answers to a JSON file."""
    data = []
    for r in results:
        data.append({
            "model": r.model,
            "scenario": r.scenario,
            "question": r.question,
            "category": r.category,
            "answer": r.answer,
            "elapsed_sec": round(r.elapsed_sec, 2),
            "composite_score": r.composite_score,
            "keyword_score": round(r.keyword_score, 2),
            "keywords_found": r.keywords_found,
            "keywords_missed": r.keywords_missed,
            "factual_correct": r.factual_correct,
            "hallucination_score": round(r.hallucination_score, 2),
            "hallucinations_found": r.hallucinations_found,
            "word_count": r.word_count,
        })

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n  Detailed results saved to {output_path}")


def print_worst_answers(results: list[Result], n: int = 5):
    """Print the worst-performing answers for review."""
    worst = sorted(results, key=lambda r: (r.composite_score, -r.elapsed_sec))[:n]
    print(f"\n{'='*78}")
    print(f"  WORST {n} ANSWERS (for manual review)")
    print(f"{'='*78}")
    for i, r in enumerate(worst, 1):
        print(f"\n  {i}. [{r.model}] {r.scenario} — {r.question}")
        flags = [f"Score: {r.composite_score:.0f}/100", f"Time: {r.elapsed_sec:.1f}s"]
        if r.factual_correct is not None:
            flags.append("CORRECT" if r.factual_correct else "WRONG ANSWER")
        if r.hallucinations_found:
            flags.append(f"Hallucinated: {r.hallucinations_found[:3]}")
        if r.keywords_missed:
            flags.append(f"Missing: {r.keywords_missed}")
        print(f"     {' | '.join(flags)}")
        preview = r.answer[:300].replace("\n", "\n     ")
        print(f"     Answer: {preview}{'...' if len(r.answer) > 300 else ''}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Benchmark Ollama models for Push Fight RAG referee")
    parser.add_argument("--models", nargs="+", default=None,
                        help="Specific models to test (default: all)")
    parser.add_argument("--small", action="store_true", help="Test only small models")
    parser.add_argument("--medium", action="store_true", help="Test only medium models")
    parser.add_argument("--large", action="store_true", help="Test only large models")
    parser.add_argument("--pull", action="store_true", help="Pull missing models before testing")
    parser.add_argument("--quick", action="store_true", help="Run fewer questions (2 per scenario)")
    _default_output = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.json")
    parser.add_argument("--output", default=_default_output,
                        help="Path for detailed JSON results (default: benchmark/benchmark_results.json)")
    args = parser.parse_args()

    # Determine which models to test
    if args.models:
        models = args.models
    elif args.small:
        models = SMALL_MODELS
    elif args.medium:
        models = MEDIUM_MODELS
    elif args.large:
        models = LARGE_MODELS
    else:
        models = ALL_MODELS

    print("=" * 70)
    print("  PUSH FIGHT — OLLAMA MODEL BENCHMARK")
    print("=" * 70)
    print(f"\n  Models to test: {', '.join(models)}")

    # Check installed models
    installed = get_installed_models()
    missing = [m for m in models if m not in installed]

    if missing:
        print(f"  Missing models: {', '.join(missing)}")
        if args.pull:
            for m in missing:
                if pull_model(m):
                    installed.add(m)
            # Filter to only installed models
            models = [m for m in models if m in installed]
        else:
            print(f"  Skipping missing models. Use --pull to download them.")
            models = [m for m in models if m in installed]

    if not models:
        print("\n  No models available. Install models with: ollama pull <model>")
        sys.exit(1)

    print(f"\n  Running benchmark with: {', '.join(models)}")

    results = run_benchmark(models, quick=args.quick)

    print_summary(results)
    print_worst_answers(results)
    save_detailed_results(results, args.output)

    print(f"\n  Done! {len(results)} total answers benchmarked.")


if __name__ == "__main__":
    main()
