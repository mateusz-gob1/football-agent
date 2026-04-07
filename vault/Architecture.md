# Architecture

## System Overview

Proactive intelligence layer for football agents managing player portfolios. Monitors market value, media coverage, and contract status — generates weekly briefings with actionable recommendations.

**Target user:** Football agent managing 20–50 players simultaneously.

**Core value proposition:** Existing tools (ATHLIVO, ScoutDecision) are passive — they store data but don't proactively monitor or alert. This system fills that gap with LLM-based intelligence.

---

## Data Sources

| Source | Data | Method |
|---|---|---|
| NewsAPI | Articles, media coverage | REST API |
| Transfermarkt | Market value, contract expiry | Scraping |
| API-Football | Goals, assists, minutes, ratings | REST API |

---

## LangGraph Flow

```
[START]
   ↓
[load_players]
   Load player roster from local store (name, club, position)
   ↓
[fetch_data]
   For each player (parallel):
   - NewsAPI → recent articles
   - Transfermarkt → market value + contract date
   - API-Football → last 10 matches stats
   ↓
[embed_and_store]
   Chunk articles → embed → store in ChromaDB
   (incremental — old articles preserved for trend analysis)
   ↓
[analyze_sentiment]
   LLM classifies sentiment per article + overall per player
   Model: gemini-2.5-flash-lite (cost-optimized)
   ↓
[detect_alerts]
   Rule-based checks:
   - Contract expiring within 6 months?
   - Market value drop > 10%?
   - Negative sentiment spike?
   ↓
[generate_briefing]
   LLM generates per-player report with recommended actions
   Context: RAG query from ChromaDB + structured data
   Model: gemini-2.5-flash (quality-optimized)
   ↓
[human_review]
   INTERRUPT — agent reviews and approves before any action
   ↓
[END]
```

---

## Model Routing Strategy

Two models used intentionally:

| Stage | Model | Reason |
|---|---|---|
| Sentiment classification | `gemini-2.5-flash-lite` | Simple classification, cost $0.10/$0.40 per 1M tokens |
| Briefing generation | `gemini-2.5-flash` | Complex synthesis, higher quality needed |

This reduces cost per full portfolio run while maintaining output quality where it matters.

---

## Tech Stack

| Technology | Role |
|---|---|
| LangGraph | Agent orchestration, conditional logic, human-in-the-loop |
| LangFuse | Observability — traces, cost tracking, latency |
| LangChain + ChromaDB | RAG layer — article storage and retrieval |
| RAGAS | Evaluation framework |
| Streamlit | Demo UI |
| Docker | Reproducible deployment |

---

## Key Design Decisions

See `Architecture-Decisions.md` for full rationale on each decision.

1. Sentiment and briefing generation are separate nodes (testability, replaceability)
2. RAG over full-context injection (cost at scale)
3. ChromaDB stores incrementally — enables trend analysis across weeks
4. Human-in-the-loop before any recommendation is acted on
