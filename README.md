# Football Agent Intelligence System

Proactive monitoring and intelligence layer for football agents managing player portfolios.

## What it does

Football agents typically manage 20–50 players simultaneously, monitoring their market value, media coverage, and contract status manually. This system automates that monitoring and surfaces actionable alerts before situations become urgent.

- Tracks player market value changes via Transfermarkt
- Monitors media coverage and sentiment via NewsAPI
- Alerts on expiring contracts
- Generates weekly per-player briefings with recommended actions
- Human-in-the-loop approval before any recommendation is acted on

## Stack

- **LangGraph** — agent orchestration
- **LangChain + ChromaDB** — RAG layer
- **LangFuse** — observability, cost tracking, latency
- **RAGAS** — evaluation
- **Streamlit** — demo UI

## Status

Work in progress.
