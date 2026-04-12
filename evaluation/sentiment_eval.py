"""
Sentiment evaluation — LLM-as-judge.

Fetches articles for a sample of players, then:
1. Judge model (claude-sonnet-4-6) classifies each article independently → ground truth
2. Each candidate model classifies the same article
3. Agreement rate per candidate is computed and reported

Results saved to evaluation/results/sentiment_eval_{date}.json
Cost and latency per model tracked via LangFuse.
"""

import os
import json
import time
from datetime import date
from pathlib import Path
from dataclasses import dataclass, asdict

from langfuse.openai import OpenAI
from langfuse import observe
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL"),
)

JUDGE_MODEL = "anthropic/claude-sonnet-4-6"

CANDIDATE_MODELS = [
    "google/gemini-2.5-flash-lite-preview-09-2025",
    "google/gemini-2.5-flash",
    "anthropic/claude-haiku-4-5",
    "openai/gpt-4o-mini",
]

# Players used for article sampling — varied clubs and coverage types
SAMPLE_PLAYERS = [
    ("Lamine Yamal",    "FC Barcelona"),
    ("Ruben Dias",      "Manchester City"),
    ("Pedro Neto",      "Chelsea"),
    ("Joao Neves",      "Paris Saint-Germain"),
    ("Bradley Barcola", "Paris Saint-Germain"),
    ("Vitinha",         "Paris Saint-Germain"),
]

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

SENTIMENT_LABELS = {"positive", "negative", "neutral"}


@dataclass
class ArticleEval:
    player: str
    title: str
    description: str
    judge_label: str
    candidate_labels: dict[str, str]  # model_name -> label
    candidate_reasons: dict[str, str]


def classify_article(model: str, player_name: str, title: str, description: str) -> tuple[str, str]:
    """Run a single-article sentiment classification. Returns (label, reason)."""
    prompt = f"""Classify the media sentiment for football player {player_name} based on this article.

Title: {title}
Description: {description}

Return JSON with exactly these fields:
{{
  "sentiment": "positive" | "negative" | "neutral",
  "reason": "one sentence, max 15 words"
}}

Rules:
- sentiment reflects how this article portrays {player_name} specifically
- if the article is not about {player_name} directly, classify as neutral
- respond with JSON only, no markdown fences"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    content = response.choices[0].message.content or ""

    # Strip markdown fences if present (some models wrap JSON in ```json ... ```)
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        return "neutral", ""

    label = raw.get("sentiment", "neutral").lower()
    if label not in SENTIMENT_LABELS:
        label = "neutral"
    reason = raw.get("reason", "")
    return label, reason


@observe(name="sentiment_eval_judge")
def get_judge_label(player_name: str, title: str, description: str) -> str:
    label, _ = classify_article(JUDGE_MODEL, player_name, title, description)
    return label


@observe(name="sentiment_eval_candidate")
def get_candidate_label(model: str, player_name: str, title: str, description: str) -> tuple[str, str]:
    return classify_article(model, player_name, title, description)


def run_evaluation(articles_per_player: int = 6) -> None:
    from tools.news_fetcher import fetch_player_news

    print(f"Sentiment Evaluation — LLM-as-judge")
    print(f"Judge: {JUDGE_MODEL}")
    print(f"Candidates: {len(CANDIDATE_MODELS)} models")
    print(f"Players: {len(SAMPLE_PLAYERS)}, ~{articles_per_player} articles each")
    print("=" * 60)

    evals: list[ArticleEval] = []

    for player_name, club in SAMPLE_PLAYERS:
        print(f"\nFetching articles: {player_name}...")
        articles = fetch_player_news(player_name, club=club)
        sample = articles[:articles_per_player]
        print(f"  {len(sample)} articles fetched")

        for article in sample:
            title = article.title or ""
            description = article.description or ""
            if not title:
                continue

            print(f"  Evaluating: {title[:60]}...")

            # Judge classifies independently
            judge_label = get_judge_label(player_name, title, description)
            time.sleep(0.5)

            candidate_labels = {}
            candidate_reasons = {}
            for model in CANDIDATE_MODELS:
                label, reason = get_candidate_label(model, player_name, title, description)
                candidate_labels[model] = label
                candidate_reasons[model] = reason
                time.sleep(0.3)

            evals.append(ArticleEval(
                player=player_name,
                title=title,
                description=description,
                judge_label=judge_label,
                candidate_labels=candidate_labels,
                candidate_reasons=candidate_reasons,
            ))

    # ── Compute agreement rates ────────────────────────────────────────────────
    total = len(evals)
    print(f"\n{'=' * 60}")
    print(f"Results — {total} articles evaluated\n")

    model_results = {}
    for model in CANDIDATE_MODELS:
        matches = sum(
            1 for e in evals
            if e.candidate_labels.get(model) == e.judge_label
        )
        agreement = matches / total if total else 0
        model_results[model] = {
            "agreement_rate": round(agreement, 3),
            "matches": matches,
            "total": total,
        }

    # Print table
    header = f"{'Model':<50} {'Agreement':>10} {'Matches':>10}"
    print(header)
    print("-" * len(header))
    for model, res in sorted(model_results.items(), key=lambda x: -x[1]["agreement_rate"]):
        short = model.split("/")[-1][:45]
        print(f"{short:<50} {res['agreement_rate']:>9.1%} {res['matches']:>5}/{res['total']}")

    # ── Save results ───────────────────────────────────────────────────────────
    output = {
        "date": str(date.today()),
        "judge_model": JUDGE_MODEL,
        "candidate_models": CANDIDATE_MODELS,
        "sample_players": [p for p, _ in SAMPLE_PLAYERS],
        "total_articles": total,
        "model_results": model_results,
        "article_evals": [asdict(e) for e in evals],
    }

    out_path = RESULTS_DIR / f"sentiment_eval_{date.today()}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {out_path}")
    print("Check LangFuse for per-model cost and latency breakdown.")


if __name__ == "__main__":
    run_evaluation(articles_per_player=6)
