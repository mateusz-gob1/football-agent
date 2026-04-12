"""
RAGAS evaluation of the RAG pipeline.

Measures whether the ChromaDB retrieval + briefing generation pipeline
produces faithful, relevant outputs grounded in retrieved article context.

Metrics (both reference-free — no manual ground truth needed):
- faithfulness:      briefing claims are supported by the retrieved articles
- answer_relevancy:  briefing addresses the monitoring query

Why these two:
- context_precision requires a reference answer (ground truth) → skipped
- faithfulness + answer_relevancy cover the two things that matter:
  (1) the model doesn't hallucinate beyond the articles
  (2) the output is relevant to the agent's actual question

LLM judge: google/gemini-2.5-flash via OpenRouter
Embeddings: sentence-transformers/all-MiniLM-L6-v2 (local, same as main pipeline)

Results saved to evaluation/results/ragas_eval_{date}.json
"""

import os
import json
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from ragas import evaluate, EvaluationDataset, SingleTurnSample
from ragas.metrics._faithfulness import Faithfulness
from ragas.metrics._answer_relevance import AnswerRelevancy
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

load_dotenv()

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

DEMO_DATA_PATH = Path(__file__).parent.parent / "data" / "demo_data.json"

EVAL_PLAYERS = [
    "Lamine Yamal",
    "Ruben Dias",
    "Pedro Neto",
    "Joao Neves",
    "Bradley Barcola",
]

JUDGE_MODEL = "google/gemini-2.5-flash"


def get_contexts_from_chromadb(player_name: str, k: int = 5) -> list[str]:
    try:
        from tools.vector_store import retrieve_context
        raw = retrieve_context(player_name, k=k)
        if not raw or raw == "No stored articles found.":
            return []
        return [line.strip() for line in raw.split("\n") if line.strip()]
    except Exception:
        return []


def get_contexts_from_demo(player: dict) -> list[str]:
    details = player.get("sentiment_details") or []
    return [
        f"{d['title']}. {d.get('reason', '')}"
        for d in details
        if d.get("title")
    ]


def build_structured_context(p: dict) -> list[str]:
    """
    Format the structured data that was injected into the briefing prompt
    (stats, market value, contract, sentiment) as context strings.
    This allows RAGAS faithfulness to verify ALL claims in the briefing,
    not just those traceable to NewsAPI articles.
    """
    contexts = []

    # Season stats
    stats_parts = []
    if p.get("appearances") is not None:
        stats_parts.append(f"{p['appearances']} appearances")
    if p.get("goals") is not None:
        stats_parts.append(f"{p['goals']} goals")
    if p.get("assists") is not None:
        stats_parts.append(f"{p['assists']} assists")
    if p.get("minutes"):
        stats_parts.append(f"{p['minutes']} minutes played")
    if p.get("league"):
        stats_parts.append(f"league: {p['league']}")
    if stats_parts:
        contexts.append(f"Season statistics for {p['name']}: {', '.join(stats_parts)}.")

    # Market value and contract
    market_parts = []
    if p.get("market_value_eur") is not None:
        market_parts.append(f"market value €{p['market_value_eur']}M")
    if p.get("contract_expires"):
        market_parts.append(f"contract expires {p['contract_expires']}")
    if p.get("days_until_expiry") is not None:
        market_parts.append(f"{p['days_until_expiry']} days until contract expiry")
    if market_parts:
        contexts.append(f"Market and contract data for {p['name']}: {', '.join(market_parts)}.")

    # Sentiment summary
    sentiment = p.get("sentiment_overall", "")
    articles_count = p.get("articles_count", 0)
    if sentiment:
        contexts.append(
            f"Media coverage for {p['name']}: overall sentiment is {sentiment}, "
            f"based on {articles_count} articles this week."
        )

    # Alerts
    alerts = p.get("alerts") or []
    if alerts:
        contexts.append(f"Active alerts for {p['name']}: {'; '.join(alerts)}.")

    return contexts


def run_evaluation() -> None:
    print("RAGAS Evaluation — RAG Pipeline Quality")
    print(f"Judge LLM: {JUDGE_MODEL}")
    print(f"Metrics: faithfulness, answer_relevancy")
    print("=" * 60)

    with open(DEMO_DATA_PATH, encoding="utf-8") as f:
        demo = json.load(f)

    players_by_name = {p["name"]: p for p in demo["players"]}

    samples = []
    player_names_used = []
    skipped = []

    for player_name in EVAL_PLAYERS:
        p = players_by_name.get(player_name)
        if not p:
            print(f"  Skipping {player_name} — not in demo data")
            skipped.append(player_name)
            continue

        briefing = p.get("briefing") or ""
        if not briefing:
            print(f"  Skipping {player_name} — no briefing in demo data")
            skipped.append(player_name)
            continue

        article_contexts = get_contexts_from_chromadb(player_name, k=5)
        if not article_contexts:
            article_contexts = get_contexts_from_demo(p)
            source = "demo_data"
        else:
            source = "chromadb"

        structured_contexts = build_structured_context(p)
        contexts = article_contexts + structured_contexts

        if not contexts:
            print(f"  Skipping {player_name} — no context available")
            skipped.append(player_name)
            continue

        print(f"  {player_name}: {len(article_contexts)} article chunks ({source}) + {len(structured_contexts)} structured")

        user_input = (
            f"What is the current performance, media coverage, and contract status "
            f"for {player_name} this week? What actions should the agent take?"
        )

        samples.append(SingleTurnSample(
            user_input=user_input,
            retrieved_contexts=contexts,
            response=briefing,
        ))
        player_names_used.append(player_name)

    if not samples:
        print("\nNo samples to evaluate — run the live pipeline first to populate ChromaDB.")
        return

    print(f"\nEvaluating {len(samples)} players...")

    llm_wrapper = LangchainLLMWrapper(ChatOpenAI(
        model=JUDGE_MODEL,
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base=os.getenv("OPENROUTER_BASE_URL"),
        temperature=0,
    ))
    emb_wrapper = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )

    faithfulness_metric = Faithfulness(llm=llm_wrapper)
    answer_relevancy_metric = AnswerRelevancy(llm=llm_wrapper, embeddings=emb_wrapper)

    dataset = EvaluationDataset(samples=samples)
    results = evaluate(
        dataset=dataset,
        metrics=[faithfulness_metric, answer_relevancy_metric],
    )
    scores = results.to_pandas()

    # ── Print results ──────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("Results\n")
    print(f"{'Player':<25} {'Faithfulness':>14} {'Ans.Relevancy':>14}")
    print("-" * 55)
    for i, name in enumerate(player_names_used):
        row = scores.iloc[i]
        print(
            f"{name:<25}"
            f"{row.get('faithfulness', float('nan')):>14.3f}"
            f"{row.get('answer_relevancy', float('nan')):>14.3f}"
        )
    print("-" * 55)
    print(
        f"{'MEAN':<25}"
        f"{scores['faithfulness'].mean():>14.3f}"
        f"{scores['answer_relevancy'].mean():>14.3f}"
    )

    # ── Save results ───────────────────────────────────────────────────────────
    output = {
        "date": str(date.today()),
        "judge_model": JUDGE_MODEL,
        "metrics": ["faithfulness", "answer_relevancy"],
        "note": "context_precision excluded — requires reference (ground truth)",
        "players_evaluated": player_names_used,
        "players_skipped": skipped,
        "aggregate": {
            "faithfulness": round(float(scores["faithfulness"].mean()), 3),
            "answer_relevancy": round(float(scores["answer_relevancy"].mean()), 3),
        },
        "per_player": scores.to_dict(orient="records"),
    }

    out_path = RESULTS_DIR / f"ragas_eval_{date.today()}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    run_evaluation()
