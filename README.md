# Football Agent Intelligence System

Proactive AI monitoring layer for football agents managing player portfolios. Built with LangGraph, LangFuse, and RAG — deployed as a live demo.

**Live demo:** https://huggingface.co/spaces/Matigob/football-agent

---

## Problem

Football agents manage 20–50 players simultaneously — tracking market value, media coverage, and contract status manually across Transfermarkt, Google News, and Excel. Existing tools (ATHLIVO, ScoutDecision) store data but don't proactively monitor or alert.

This system adds an agentic intelligence layer that monitors each player's situation and surfaces actionable briefings before situations become urgent.

---

## What it does

- Monitors market value changes per player (Transfermarkt)
- Tracks media coverage and runs sentiment analysis (NewsAPI)
- Alerts on expiring contracts, low coverage, rating drops
- Generates weekly per-player briefings with recommended actions
- Runs dual-model briefing (Gemini Flash + Claude Sonnet) with automated critique and retry loop

---

## Architecture

```
START
  │
  ▼
fetch_data          — NewsAPI + Transfermarkt + API-Football + sentiment + ChromaDB store
  │
  ▼
detect_alerts       — rule-based checks (contract, sentiment, rating, coverage)
  │
  ▼
generate_briefings  — Gemini Flash + Claude Sonnet in parallel (RAG context injected)
  │
  ▼
critique_briefings  — Gemini Flash Lite scores both (0–9), selects winner
  │
  ▼
should_retry        — retry if both fail and attempts < 2, else END
  │
  ▼
END
```

---

## Stack

| Technology | Role |
|---|---|
| LangGraph | Agent orchestration — 4 nodes + conditional edges + retry loop |
| LangFuse | Observability — traces, cost tracking, latency per run |
| LangChain + ChromaDB | RAG layer — article embeddings + semantic retrieval |
| RAGAS | Evaluation — faithfulness and answer relevancy |
| FastAPI | Backend API serving demo data |
| Docker | Containerized deployment |

---

## Evaluation results

| Metric | Value |
|---|---|
| Sentiment accuracy (LLM-as-judge, 36 articles) | 97.2% |
| RAG faithfulness (RAGAS, 5 players) | 0.641 |
| RAG answer relevancy (RAGAS, 5 players) | 0.709 |
| Cost per run — 20 players, 128 articles | ~$0.024 |

---

## Run locally

```bash
git clone https://github.com/Matigob/football-agent
cd football-agent
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env  # add your API keys
```

**Required API keys** (add to `.env`):
- `OPENROUTER_API_KEY` — LLM calls (OpenRouter)
- `NEWSAPI_KEY` — media monitoring
- `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` — observability

**Run the agent:**
```bash
python -m agents.graph
```

**Run the demo dashboard:**
```bash
uvicorn api.main:app --reload
# open http://localhost:8000
```

---

## Project structure

```
football-agent/
├── agents/
│   ├── graph.py          # LangGraph StateGraph definition
│   ├── nodes.py          # fetch_data, detect_alerts, generate_briefings, critique_briefings
│   └── state.py          # AgentState + PlayerResult TypedDicts
├── tools/
│   ├── transfermarkt.py  # market value + contract scraper
│   ├── news_fetcher.py   # NewsAPI integration
│   ├── sentiment.py      # LLM sentiment analysis
│   ├── vector_store.py   # ChromaDB store + retrieve
│   ├── stats_fetcher.py  # API-Football stats
│   └── history_store.py  # market value snapshot history
├── evaluation/
│   ├── ragas_eval.py     # RAGAS faithfulness + relevancy
│   └── sentiment_eval.py # LLM-as-judge sentiment accuracy
├── api/
│   └── main.py           # FastAPI backend
├── frontend/             # vanilla JS dashboard
├── data/
│   └── demo_data.json    # pre-generated demo portfolio
├── vault/                # Obsidian documentation
├── Dockerfile
└── scripts/
    └── rebuild_demo.py   # regenerate demo_data.json
```
