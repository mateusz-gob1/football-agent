# Architecture Decisions

## ADR-001: Separate sentiment analysis from briefing generation

**Decision:** Two distinct nodes/modules — `sentiment.py` for classification, briefing generation later in the graph.

**Why:** Single responsibility. Easier to test each step independently. Easier to swap the sentiment model without touching briefing logic. In the LangGraph diagram, the separation is visible — better for explaining the architecture in interviews.

**Trade-off:** Two LLM calls per player instead of one. Acceptable given cost difference between models used.

---

## ADR-002: RAG over full-context injection

**Decision:** Articles are embedded into ChromaDB. Briefing generation queries the vector store for relevant context instead of injecting all articles into the prompt.

**Why:** At scale (30 players × 10 articles × 7 days = 2,100 articles) full injection becomes expensive and hits context limits. RAG retrieves only the most relevant chunks.

**Trade-off:** Added complexity (embedding pipeline, vector store). Justified at portfolio scale.

---

## ADR-003: Incremental ChromaDB storage

**Decision:** New articles are added to ChromaDB on each run. Old articles are not deleted.

**Why:** Enables trend analysis — system can compare this week's sentiment against previous weeks. Historical context makes briefings more insightful.

**Trade-off:** Storage grows over time. Acceptable for a portfolio of 50 players over months.

---

## ADR-004: Model routing — two models for two tasks

**Decision:** `gemini-2.5-flash-lite` for sentiment classification, `gemini-2.5-flash` for briefing generation.

**Why:** Sentiment is a simple classification task — lightweight model is sufficient and cheaper ($0.10/$0.40 per 1M tokens). Briefing requires complex synthesis — quality matters more than cost at this single step.

**Result:** Cost optimization without quality compromise at the output stage.

---

## ADR-005: API-Football for player statistics

**Decision:** Added API-Football as a third data source for goals, assists, minutes, ratings.

**Why:** Contract negotiation context requires performance data. "Player scored 8 goals in last 10 matches" is a material fact for an agent's negotiation strategy — not available from NewsAPI or Transfermarkt.

**Constraint:** Free tier = 100 requests/day. Handled by caching stats locally, refreshing once per system run.

---

## ADR-006: FastAPI + vanilla JS instead of Streamlit

**Decision:** Custom frontend (HTML/CSS/JS) with a FastAPI backend instead of Streamlit.

**Why:** Portfolio quality. Streamlit looks like a data science notebook, not a product. A custom UI demonstrates frontend competence and looks professional in demo recordings. Streamlit also imposes layout constraints that make building a multi-view dashboard (sidebar nav, player detail pages, KPI cards) unnecessarily difficult.

**Trade-off:** More code to write and maintain. Justified for a public demo that recruiters will see.

---

## ADR-007: Demo mode with static pre-generated data

**Decision:** The public demo serves `demo_data.json` (pre-generated on 2026-04-08) instead of running the live pipeline. `/api/generate` returns HTTP 403 with a message directing users to clone the repo and run locally with their own API keys.

**Why:** Protects API keys. Avoids Transfermarkt scraping costs on a public endpoint. Gives full control over what the demo shows — no risk of a failed scrape breaking the demo mid-recording.

**Trade-off:** Demo data goes stale over time. Acceptable — the code and architecture are the portfolio artifact, not the live data.

---

## ADR-008: Transfermarkt URL mandatory when adding players

**Decision:** `transfermarkt_url` is a required field in the Player dataclass. A player cannot be added without it.

**Why:** Name ambiguity is a real problem — many players share surnames (multiple "Fernandes", "Silva", "Ramos"). Automatic name-based search resolves to the wrong player silently. A URL copied directly from the browser guarantees the correct player regardless of name variations or search ranking.

**Trade-off:** The user must manually look up the URL once per player. Acceptable — it is a one-time operation and prevents bad data silently corrupting the pipeline.

---

## ADR-009: cloudscraper for Transfermarkt, Playwright as next step

**Decision:** Use cloudscraper for Cloudflare bypass. Known limitation: Cloudflare Turnstile (HTTP 405) requires real browser execution and cannot be solved by cloudscraper.

**Why:** cloudscraper handles standard Cloudflare JS challenges with zero setup — sufficient for a weekly cadence with a small portfolio. Rate limit from testing: ~10 requests before blocking. Production usage (10–12 players/week with 2s delays between requests) does not trigger the block.

**Next step:** Migrate to Playwright for full browser automation to eliminate 405 errors on Turnstile-protected pages.

**Trade-off:** Current implementation fails on pages where TM activates Turnstile. Fallback: scrape with delays, accept occasional failures, retry next weekly run.

---

## ADR-010: Initials avatars instead of API-Football photos

**Decision:** Player photos replaced with styled colored circles showing player initials (e.g. "LY" on Barcelona red for Lamine Yamal).

**Why:** API-Football player IDs were producing photo mismatches — the wrong player's photo was being displayed. Initials avatars are always correct because they derive from the player name in state. Zero external dependencies. The color is tied to the player's club color, making the avatar informative rather than decorative.

**Trade-off:** Less visual richness than real photos. Acceptable given the correctness guarantee and zero-dependency benefit.
