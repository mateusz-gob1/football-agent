# Evaluation Log

## Planned Experiments

### [TODO — Block 3] Model comparison for sentiment analysis
**Goal:** Find optimal model for accuracy vs cost

**Plan:**
1. Collect ~50 articles across different players (simple and complex, varied coverage types)
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

## System Metrics (current state)

| Metric | Value | Notes |
|---|---|---|
| Cost per sentiment analysis | $0.000288 | 9 articles, gemini-2.5-flash-lite |
| Latency p50 (sentiment) | 2.40s | LangFuse dashboard |
| Total cost (3 players, full run) | ~$0.002 | estimated |
| ChromaDB articles stored | 9 | Mbappe only, grows each run |

## Completed Experiments

### [2026-04-07] Initial validation — sentiment_analysis, Mbappe
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
