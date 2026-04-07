# Agent Behavior

## Graph Overview

The system is implemented as a LangGraph StateGraph. One run processes one or more players — the same graph handles both portfolio runs (all players) and on-demand runs (single player).

```
[START]
   ↓
[fetch_data]         — news + stats + market data per player
   ↓
[detect_alerts]      — rule-based checks, no LLM
   ↓                     ↘ (no results → END)
[generate_briefings] — LLM generates per-player report using RAG context
   ↓
[human_review]       — INTERRUPT: waits for agent approval
   ↓
[END]
```

## Nodes

### fetch_data
Iterates over all players in state. For each player:
- Fetches articles from NewsAPI (`tools/news_fetcher.py`)
- Embeds and stores new articles in ChromaDB (`tools/vector_store.py`)
- Analyzes sentiment via LLM (`tools/sentiment.py`)
- Fetches season stats from API-Football (`tools/stats_fetcher.py`)
- Scrapes market value and contract date from Transfermarkt (`tools/transfermarkt.py`)

LangFuse trace: `fetch_data`

### detect_alerts
Rule-based checks — no LLM call. Fires alerts when:
- `sentiment_overall == "negative"` → negative coverage alert
- `sentiment_overall == "no coverage"` → visibility alert
- `rating < 7.0` → below-average performance alert
- `days_until_expiry < 180` → contract expiring soon alert
- `days_until_expiry < 0` → contract expired alert

### generate_briefings
For each player, builds a prompt with:
- Season statistics
- Market value and contract data
- RAG context (top 5 relevant articles from ChromaDB)
- Sentiment summary and alerts

Model: `google/gemini-2.5-flash` (stronger model for final output quality)
LangFuse trace: `generate_briefings`

### human_review
Interrupt node — LangGraph pauses execution here using `interrupt_before=["human_review"]`. The agent reviews all briefings, then resumes with `app.invoke(None, config)` to complete the run.

## Running the System

**Portfolio run (all players):**
```python
app.invoke({"players": [p.__dict__ for p in load_players()], ...}, config=config)
```

**On-demand run (single player):**
```python
app.invoke({"players": [mbappe.__dict__], ...}, config=config)
```

Same graph, different input.

## State Schema

```python
class AgentState(TypedDict):
    players: list[dict]
    results: list[PlayerResult]
    pending_briefings: list[str]
    human_approved: bool
```

Each `PlayerResult` contains: name, club, articles_count, sentiment, goals, assists, appearances, rating, market_value_eur, contract_expires, days_until_expiry, alerts, briefing.

## Adding a Player

```python
from tools.player_store import add_player

add_player(
    name="Bruno Fernandes",
    club="Manchester United",
    position="Midfielder",
    transfermarkt_url="https://www.transfermarkt.com/bruno-fernandes/profil/spieler/240306"
)
```

`transfermarkt_url` is mandatory — must be copied manually from transfermarkt.com. This guarantees the correct player is tracked regardless of name ambiguity. API-Football ID is resolved automatically.
