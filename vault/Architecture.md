# Architecture

## System Overview

Football Agent Intelligence System is a proactive intelligence layer for football agents managing player portfolios of 20–50 players. It replaces manual monitoring (Transfermarkt + Google News + Excel) with an automated pipeline that collects data, detects signals, and generates actionable weekly briefings per player.

**Target user:** Football agent (e.g. Gestifute-style firm). Manages a portfolio of players. Needs to know — before it becomes urgent — about contract expiry windows, sentiment drops, and market value changes.

**Value vs competitors:** ATHLIVO and ScoutDecision are passive — they store and organize data. This system actively monitors, detects alerts, and generates LLM briefings with recommended actions. Neither competitor uses agentic AI or proactive alerting (verified as of 2026-04).

---

## Data Sources

| Source | What it provides | Access method |
|---|---|---|
| NewsAPI | News articles per player (last 7 days by default) | REST API, exact-match query |
| Transfermarkt | Market value, contract expiry, season stats per competition, value history | Web scraping (cloudscraper) |
| API-Football | Goals, assists, minutes, match ratings | REST API, local JSON cache |

---

## LangGraph Flow

```
┌─────────────────────────────────────────────────────────┐
│                     StateGraph                          │
│                                                         │
│  START                                                  │
│    │                                                    │
│    ▼                                                    │
│  fetch_data                                             │
│  (NewsAPI + TM scrape + API-Football + sentiment        │
│   + ChromaDB store)                                     │
│    │                                                    │
│    ▼                                                    │
│  detect_alerts                                          │
│  (contract expiry, sentiment drop, no coverage,         │
│   below-average rating)                                 │
│    │                                                    │
│    ▼                                                    │
│  should_generate ──── (no alerts, no briefing req) ───► END
│    │                                                    │
│    │ (alerts exist OR briefing explicitly requested)    │
│    ▼                                                    │
│  generate_briefings                                     │
│  (@observe LangFuse, RAG context, Gemini Flash)         │
│    │                                                    │
│    ▼                                                    │
│  human_review  ◄── interrupt_before                     │
│  (agent reviews alerts + briefings before any action)   │
│    │                                                    │
│    ▼                                                    │
│   END                                                   │
└─────────────────────────────────────────────────────────┘
```

`should_generate` is a conditional edge function — not a node. It routes to `generate_briefings` or `END` based on state.

The graph uses `interrupt_before=["human_review"]` — execution pauses before the human review node. The agent inspects briefings in the frontend, then resumes by invoking `app.invoke(None, config)`.

---

## Model Routing

| Task | Model | Why |
|---|---|---|
| Sentiment classification | `google/gemini-2.5-flash-lite-preview-09-2025` | Simple classification — cheap model sufficient |
| Briefing generation | `google/gemini-2.5-flash` | Complex synthesis — quality over cost at this stage |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local) | Zero API cost, runs on CPU, no external dependency |

All LLM calls route through OpenRouter. Cost and latency tracked per run via LangFuse.

---

## Tech Stack

| Technology | Role |
|---|---|
| LangGraph | Stateful multi-node orchestration, conditional routing, human-in-the-loop |
| LangFuse | Observability — traces, cost per run, latency, prompt versioning |
| LangChain | LLM abstraction, RAG pipeline |
| ChromaDB | Vector store — article embeddings, duplicate detection |
| sentence-transformers (all-MiniLM-L6-v2) | Local embeddings — no API cost |
| FastAPI | Backend API serving agent runs and player data |
| HTML/CSS/JS (vanilla) | Frontend — sidebar nav, KPI cards, player detail view, no framework |
| cloudscraper | Cloudflare bypass for Transfermarkt scraping |
| NewsAPI | Media monitoring |
| Transfermarkt | Market value, contract data, season stats per competition, value history |
| API-Football | Player match statistics (cached locally) |
| Docker | Containerized deployment |
| Hugging Face Spaces | Public demo hosting |

---

## Demo Mode

The public demo serves pre-generated `data/demo_data.json` containing 10 Gestifute players with real scraped data. The `/api/generate` endpoint returns HTTP 403 with instructions to clone the repo and run with own API keys.

This protects API keys and scraping budget while keeping a fully functional UI visible to recruiters. The demo data was generated from a live pipeline run on 2026-04-08.

Player avatars use styled initials circles with club colors (e.g. "LY" on Barcelona red for Lamine Yamal) — no external photo API, no wrong-player mismatches.

---

## Key Design Principles

1. **LangFuse from day one.** Every LLM call is observed. Cost per run is a measurable portfolio metric.
2. **Passive tools, active agent.** Tools (fetchers, scrapers) are stateless functions. The LangGraph graph owns all state and orchestration logic.
3. **Separation of concerns.** Sentiment classification and briefing generation are distinct nodes with distinct models. Each is independently testable and replaceable.
4. **RAG over full-context injection.** Articles are embedded and retrieved rather than injected wholesale. Scales to large portfolios without hitting context limits or ballooning costs.
5. **Human-in-the-loop before action.** The agent never acts without review. LangGraph `interrupt_before` enforces this structurally.
6. **Demo mode is a first-class concern.** Public demos must be stable and cost-free. Static pre-generated data is the correct solution, not a compromise.
7. **Mandatory source URLs for players.** `transfermarkt_url` is required when adding a player. Prevents silent ID mismatches caused by name ambiguity.
