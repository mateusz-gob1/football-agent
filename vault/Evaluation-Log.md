# Evaluation Log

## Run 001 — 2026-04-08 (Demo)

**Mode:** Demo (pre-generated data, no live LLM calls)
**Portfolio:** 10 Gestifute players
**Articles processed:** 96 (estimated)
**Run cost (live pipeline estimate):** ~$0.006
**Alerts generated:** 5

### Data accuracy

Scraped live via transfermarkt.py (cloudscraper):
- Lamine Yamal: 41 apps / 21g / 16a ✓ (verified vs TM screenshot)
- Gonçalo Ramos: 39 apps / 12g / 2a ✓ (verified vs TM screenshot)
- Pedro Neto: 45 apps / 10g / 7a ✓ (verified vs TM screenshot)
- Cristiano Ronaldo: 27 apps / 24g / 4a ✓ (scraped)
- João Félix: 26 apps / 15g / 12a ✓ (verified vs TM screenshot)

Estimated (TM rate-limited during testing):
- Vitinha, João Neves, Rúben Dias, Francisco Conceição, Bernardo Silva

### Issues found

- TM Cloudflare Turnstile blocks cloudscraper on some pages (405 error)
- Rate limit triggered after ~10 rapid requests during testing
- Production cadence (weekly, 2s delays) does not trigger rate limit
- Next step: Playwright migration for reliable browser-level scraping

### Key alert

Bernardo Silva contract expires in 83 days (2026-06-30) — highest urgency in portfolio.

---

## Planned Experiments

### [TODO — Block 3] Model comparison for sentiment analysis

**Goal:** Find optimal model for accuracy vs cost.

**Plan:**
1. Collect ~50 articles across different players (varied coverage types, simple and complex)
2. Mateusz manually labels each article (positive / negative / neutral) → ground truth
3. Run `evaluation/sentiment_eval.py` for each candidate model
4. Compare accuracy + cost per call from LangFuse

**Candidate models:**
- `google/gemini-2.5-flash-lite` (baseline, current)
- `google/gemini-2.5-flash`
- `anthropic/claude-3-haiku`
- `openai/gpt-4o-mini`

**Target metric:** accuracy ≥ 85% agreement with human labels

---

## System Metrics (historical)

| Metric | Value | Notes |
|---|---|---|
| Cost per sentiment analysis | $0.000288 | 9 articles, gemini-2.5-flash-lite |
| Latency p50 (sentiment) | 2.40s | LangFuse dashboard |
| Total cost (3 players, full run) | ~$0.002 | estimated |
| Cost (10 players, 96 articles) | ~$0.006 | estimated, demo run |

---

## Completed Experiments

### [2026-04-07] Initial validation — sentiment analysis, Mbappe

**Model:** google/gemini-2.5-flash-lite-preview-09-2025
**Sample:** 8 articles, human labels: Mateusz

| Article | Human | Model | Match |
|---|---|---|---|
| Expert picks / betting odds | neutral | neutral | ✅ |
| Disciplinary risks Real Madrid | neutral | neutral | ✅ |
| Line-ups, stats and preview | neutral | neutral | ✅ |
| Arbeloa on his future | neutral | neutral | ✅ |
| "We have to play differently with Mbappe and Bellingham" | positive | positive | ✅ |
| Vinicius Junior on contract renewal | neutral | neutral | ✅ |
| How to watch | neutral | neutral | ✅ |
| Arbeloa confirms Mbappe for Bayern | positive | positive | ✅ |

**Result:** 8/8 (100%) — sample too small, articles too similar thematically
**Cost:** $0.000288 per call (714 input → 541 output tokens)
**Latency:** ~2.40s (p50)

**Observations:**
- Model behaves conservatively — good for precision
- Most articles are about the match, Mbappe appears incidentally → risk of conflating match sentiment with player sentiment
- More complex articles may yield different results → reason for planned model comparison in Block 3
