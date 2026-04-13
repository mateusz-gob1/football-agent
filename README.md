<div align="center">
  <img src="docs/assets/logo.svg" width="80" alt="Football Agent Logo" />
  <h1>Football Agent Intelligence System</h1>
  <p>Proactive AI monitoring for football agents managing player portfolios</p>

  <p>
    <a href="https://huggingface.co/spaces/Matigob/football-agent">
      <img src="https://img.shields.io/badge/🤗%20Live%20Demo-HuggingFace-orange?style=for-the-badge" alt="Live Demo"/>
    </a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/LangGraph-Orchestration-blue?style=flat-square"/>
    <img src="https://img.shields.io/badge/LangFuse-Observability-purple?style=flat-square"/>
    <img src="https://img.shields.io/badge/ChromaDB-RAG-green?style=flat-square"/>
    <img src="https://img.shields.io/badge/RAGAS-Evaluation-red?style=flat-square"/>
    <img src="https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python"/>
    <img src="https://img.shields.io/badge/Docker-Deployed-2496ED?style=flat-square&logo=docker"/>
  </p>
</div>

---

## Overview

Football agents manage 20–50 players simultaneously — tracking market value, media coverage, and contract status manually across Transfermarkt, Google News, and Excel.

Existing tools (ATHLIVO, ScoutDecision) store data but remain **passive** — they don't proactively monitor or generate intelligence. This system adds an agentic layer that monitors each player's situation and surfaces actionable briefings before situations become urgent.

---

## Screenshots

<img src="docs/assets/screenshot-overview.png" alt="Portfolio Overview" width="100%"/>
<em>Portfolio Overview — market values, sentiment distribution, 20 players monitored</em>

<br/><br/>

<table>
  <tr>
    <td><img src="docs/assets/screenshot-player1.png" alt="Player Detail"/></td>
    <td><img src="docs/assets/screenshot-player2.png" alt="Player Briefing"/></td>
  </tr>
  <tr>
    <td align="center"><em>Player stats, alerts, value history</em></td>
    <td align="center"><em>Weekly intelligence brief + model comparison</em></td>
  </tr>
</table>

---

## What it does

- **Market monitoring** — tracks player market value changes via Transfermarkt
- **Media intelligence** — fetches and analyzes sentiment from NewsAPI articles
- **Contract alerts** — flags contracts expiring within 180 days
- **Weekly briefings** — generates per-player intelligence briefs with recommended actions
- **Dual-model evaluation** — runs Gemini Flash and Claude Sonnet in parallel, scores both, selects the better output

---

## Architecture

```
START
  │
  ▼
fetch_data          ── NewsAPI · Transfermarkt · API-Football · sentiment · ChromaDB
  │
  ▼
detect_alerts       ── rule-based (contract expiry · sentiment · rating · coverage)
  │
  ▼
generate_briefings  ── Gemini Flash + Claude Sonnet in parallel · RAG context injected
  │
  ▼
critique_briefings  ── Gemini Flash Lite scores both 0–9 · selects winner
  │
  ▼
should_retry        ── retry if both fail AND attempts < 2 · else END
  │
  ▼
END
```

---

## Evaluation results

| Metric | Value | Method |
|---|---|---|
| Sentiment accuracy | **97.2%** | LLM-as-judge (Claude Sonnet vs 36 labelled articles) |
| RAG faithfulness | **0.641** | RAGAS — 5 players |
| RAG answer relevancy | **0.709** | RAGAS — 5 players |
| Cost per run (20 players) | **~$0.024** | LangFuse cost tracking |
| Total LangFuse traces | **504** | Across full development cycle |
| Total LLM cost (dev) | **$1.057** | LangFuse — all models combined |

**Model cost breakdown (LangFuse):**

| Model | Tokens | Cost |
|---|---|---|
| Claude Sonnet 4.6 | 66.7K | $0.460 |
| Gemini 2.5 Flash | 111K | $0.090 |
| Gemini Flash Lite | 259.9K | $0.046 |

---

## Stack

| Technology | Role |
|---|---|
| LangGraph | Agent orchestration — 4 nodes, conditional edges, retry loop |
| LangFuse | Observability — traces, cost tracking, latency per run |
| LangChain + ChromaDB | RAG — article embeddings + semantic retrieval |
| RAGAS | Evaluation — faithfulness and answer relevancy |
| FastAPI | Backend serving demo data |
| Docker | Containerized deployment on Hugging Face Spaces |

---

## Run locally

```bash
git clone https://github.com/mateusz-gob1/football-agent
cd football-agent
python -m venv .venv && .venv/Scripts/activate  # Windows
pip install -r requirements.txt
cp .env.example .env  # add your API keys
```

**Required API keys** (`.env`):

```
OPENROUTER_API_KEY=       # LLM calls via OpenRouter
NEWSAPI_KEY=              # media monitoring
LANGFUSE_PUBLIC_KEY=      # observability
LANGFUSE_SECRET_KEY=
```

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
│   ├── graph.py          # LangGraph StateGraph
│   ├── nodes.py          # fetch_data · detect_alerts · generate_briefings · critique_briefings
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
│   └── sentiment_eval.py # LLM-as-judge accuracy
├── api/main.py           # FastAPI backend
├── frontend/             # vanilla JS dashboard
├── data/demo_data.json   # pre-generated demo portfolio (20 players)
├── vault/                # project documentation
└── Dockerfile
```
