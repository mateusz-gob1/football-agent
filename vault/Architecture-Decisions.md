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

## ADR-009: Playwright for Transfermarkt (migrated from cloudscraper)

**Decision:** Replaced cloudscraper with Playwright (Chromium, headless) for Transfermarkt scraping.

**Why:** cloudscraper failed on pages protected by Cloudflare Turnstile ("Let's confirm you are human") — returned HTTP 405 or an unresolvable CAPTCHA page. Playwright launches a real browser, which passes standard Cloudflare challenges that JavaScript detection would block.

**Implementation:** Module-level browser instance initialized lazily (`_get_browser()`). One browser per pipeline run, one browser context per page fetch. `wait_until="networkidle"` gives Cloudflare time to resolve before capturing HTML.

**Remaining limitation:** Cloudflare Turnstile (interactive CAPTCHA) still blocks headless Playwright during initial testing. The `leistungsdaten` and `marktwertverlauf` pages return a human-verification page under some conditions. This is an ongoing issue without a clean solution short of `playwright-stealth` or a CAPTCHA-solving service.

**Fallback strategy:** Capology (ADR-011) covers contract expiry as an alternative data source when TM is blocked.

---

## ADR-010: Initials avatars instead of API-Football photos

**Decision:** Player photos replaced with styled colored circles showing player initials (e.g. "LY" on Barcelona red for Lamine Yamal).

**Why:** API-Football player IDs were producing photo mismatches — the wrong player's photo was being displayed. Initials avatars are always correct because they derive from the player name in state. Zero external dependencies. The color is tied to the player's club color, making the avatar informative rather than decorative.

**Trade-off:** Less visual richness than real photos. Acceptable given the correctness guarantee and zero-dependency benefit.

---

## ADR-011: Capology as contract/salary data source

**Decision:** Add Capology as a dedicated source for player salary estimates and contract expiry dates.

**Why:** Transfermarkt is the standard source for contract data but is frequently blocked by Cloudflare Turnstile. Capology is a specialized salary database that covers the top 5 European leagues and provides weekly/annual wage estimates alongside contract end dates. This fills a genuine gap in the system — salary context improves briefing quality and enables "agent should renegotiate now" type recommendations.

**Implementation:** Custom Playwright scraper in `tools/capology_fetcher.py`. ScraperFC has a Capology module but uses Selenium; Playwright is already in the stack so we avoid the dependency. League data is fetched once and cached locally in `data/capology_cache/`.

**Trade-off:** Salary figures are estimates, not official values. Not all leagues are covered (no Saudi Pro League for Ronaldo). Acceptable — estimates are good enough for briefing context and alert generation.

---

## ADR-012: SQLite for weekly value snapshots

**Decision:** Each pipeline run saves a market value snapshot per player to a local SQLite database (`data/history.db`).

**Why:** Transfermarkt provides full historical market value data via the `marktwertverlauf` page, but that page is often blocked by Cloudflare. Building our own longitudinal record — one snapshot per weekly run — gives us trend data that is independent of TM availability. Over months, this becomes a proprietary dataset of value changes with exact timestamps.

**Implementation:** `tools/history_store.py` — `save_snapshot()` called in `fetch_data` node after each TM scrape. `get_snapshots()` used to populate `value_history` in PlayerResult for chart rendering.

**Trade-off:** Data starts accumulating only from the first live pipeline run. Demo uses static `value_history` data embedded in `demo_data.json`.

---

## ADR-014: Reflection loop with dual-model briefing evaluation

**Decision:** Each player briefing is generated by two models in parallel (Gemini 2.5 Flash + Claude Sonnet 4.6). A third lightweight model (Gemini Flash Lite) scores each on three criteria (actionable 1–3, grounded 1–3, alert-aware 1–3). The higher-scoring briefing is selected as the winner. If both fail (score < 7/9), the loop retries up to 2 times with critique feedback injected into the prompt.

**Why:** Demonstrates agentic evaluation pattern — system is self-correcting, not just generating output. Creates a measurable quality signal ("Sonnet 8/9 vs Flash 6/9") that is defensible in interviews. The critique criteria are domain-specific (agent needs actionable, grounded, alert-aware output) not generic.

**UI decision:** Model comparison tabs removed from the end-user view. The agent sees only the winning briefing. The model selection is visible in the footer ("Claude Sonnet 4.6 · score 9/9") — the comparison lives in the backend for evaluation purposes.

**Trade-off:** 3 LLM calls per player instead of 1. Cost increase ~3× at briefing stage. Justified because briefing quality is the core differentiator of the system.

---

## ADR-015: Portfolio expanded to 20 players, stats from Transfermarkt (season 25/26)

**Decision:** Demo portfolio expanded from 10 to 20 Football Agent Assistant players. Stats sourced directly from Transfermarkt season 25/26 pages (screenshots → manual entry). Added `minutes` and `age` fields to the player data model.

**Why:** 10 players felt like a proof-of-concept; 20 is a realistic small agency portfolio. Season 25/26 stats are the most current available (API-Football free tier only covers up to 2024/25). Minutes played is a key metric for agents — differentiates starter vs. bench role at a glance.

**Stats included per player:** appearances, goals, assists, minutes (total across all competitions), age, contract expiry, market value.

**Rating removed from UI:** API-Football ratings are from 2024/25 (last season) — showing them next to 25/26 stats would be misleading. Removed entirely pending a live data source.

**Trade-off:** Manual data entry is not scalable. Acceptable for a demo; the production path is Transfermarkt scraping once Cloudflare is bypassed.

---

## ADR-017: Human-in-the-loop removed from graph

**Decision:** Removed `interrupt_before=["human_review"]` and the `human_review` node from the LangGraph graph. Briefings are written to state and available in the dashboard for async review — no blocking interrupt.

**Why:** The system outputs read-only intelligence reports, not irreversible actions. A blocking interrupt makes sense when an agent could send an email, trigger a transfer, or publish something — none of which this system does. Async delivery is better UX: run completes, briefings are ready whenever the agent logs in.

**Interview answer:** *"I implemented HITL with `interrupt_before`, evaluated it in practice, and removed it. HITL is the right pattern when the agent takes irreversible actions. For a read-only briefing system it adds friction without safety value. The next iteration would reintroduce it if the system gains the ability to send emails or draft contract proposals."*

---

## ADR-018: Evaluation layer — LLM-as-judge for sentiment, RAGAS for RAG

**Decision:** Two evaluation scripts in `evaluation/`:
- `sentiment_eval.py` — LLM-as-judge: claude-sonnet-4-6 classifies articles independently (ground truth), four candidate models compared against it
- `ragas_eval.py` — RAGAS faithfulness + answer_relevancy on 5 players, context = ChromaDB chunks + structured stats/contract strings

**Why LLM-as-judge instead of manual labels:** Manual labeling of 50 articles is time-consuming and introduces annotator bias. LLM-as-judge is standard practice in the industry — a stronger model's classification serves as pseudo-ground-truth. Key requirement: judge must be clearly stronger than candidates (Sonnet 4.6 vs Flash Lite/Flash/Mini/Haiku).

**Why hybrid context for RAGAS faithfulness:** The briefing prompt combines NewsAPI articles (via RAG) and structured data (Transfermarkt stats, contract). Evaluating faithfulness against articles only gave 0.32 — misleadingly low. Adding structured data as context strings raised it to 0.64, accurately reflecting what the model actually had available.

**Results (2026-04-12):**
- Sentiment: gemini-2.5-flash-lite 97.2% agreement (36 articles) → kept as production model
- RAGAS faithfulness: 0.641 | answer_relevancy: 0.709 (5 players)

---

## ADR-019: Platform renamed to Football Agent Assistant

**Decision:** Removed "Gestifute" (real company name) from the codebase. Platform brand: "Football Agent Assistant". Demo account: Jorge Mendes (name only), agency field: "Football Agent Assistant".

**Why:** Using a real company name in a public demo creates unnecessary association. Platform name as demo agency name reinforces product identity.

---

## ADR-020: Article links in Media Coverage section

**Decision:** Article titles in the Media Coverage module are clickable links (open in new tab) when a URL is available.

**Why:** An agent seeing a red dot (negative sentiment) needs to read the actual article before acting. Without links the dashboard is a dead end. Minimal change (3 lines JS), high practical value.

---

## ADR-016: Strict briefing format with robust client-side renderer

**Decision:** Briefing prompt now enforces an exact four-section format (FORM & PERFORMANCE / MEDIA INTELLIGENCE / MARKET & CONTRACT / RECOMMENDED ACTIONS) with explicit instruction to start the response with `**FORM & PERFORMANCE**` and nothing before it. The frontend renderer (`renderBriefingText`) is a line-by-line parser that strips any noise (markdown headers, metadata lines, separators, placeholder dates) regardless of model output variance.

**Why:** LLMs diverge significantly in how they format structured output — one model adds `# WEEKLY INTELLIGENCE BRIEF` headers, another adds `**PLAYER:** Joao Neves |` metadata, another uses `[Current Date]` placeholders. The combination of a strict prompt + defensive renderer makes the UI consistent regardless of which model wins.

**Implementation:** Parser iterates lines, classifies each as section header / action item / noise / paragraph. Noise lines are discarded silently. Section headers become `<div class="brief-section-header">`. Numbered items under RECOMMENDED ACTIONS become `<div class="brief-action">`.

**Trade-off:** Parser must be updated if we add new structural elements. Acceptable — the format is intentionally stable.

---

## ADR-013: Chart.js for frontend data visualization

**Decision:** Added Chart.js 4.x to the frontend for market value trend (player detail) and portfolio overview charts (bar + donut).

**Why:** Static numbers don't communicate trends. A line chart showing a player's value declining from €80M to €25M is immediately actionable for an agent. Charts also significantly improve the visual quality of the demo for recruiters — the dashboard looks like a real product, not a data table.

**Charts implemented:**
- Player detail: market value trend line (color matches player's club color)
- Overview: horizontal bar chart (portfolio value comparison) + donut (sentiment distribution)

**Trade-off:** Chart.js loaded from CDN — demo requires internet. Acceptable for a demo tool.
