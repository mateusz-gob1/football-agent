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
