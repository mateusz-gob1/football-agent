# Agent Behavior

## Graph Overview

The system is a LangGraph StateGraph. One run processes one or more players — the same graph handles portfolio runs (all players) and on-demand single-player runs.

```
START
  │
  ▼
fetch_data
  (NewsAPI + TM scrape + API-Football + sentiment + ChromaDB store)
  │
  ▼
detect_alerts
  (rule-based checks — no LLM)
  │
  ▼
should_generate ──── (no alerts, no briefing requested) ────► END
  │
  │ (alerts exist OR briefing explicitly requested)
  ▼
generate_briefings
  (@observe LangFuse, RAG context, Gemini Flash)
  │
  ▼
human_review   ◄── interrupt_before=["human_review"]
  (agent reviews briefings before any action)
  │
  ▼
END
```

`should_generate` is a conditional edge function — not a standalone node. It reads state and routes to `generate_briefings` or `END`.

---

## Nodes

### fetch_data

Iterates over all players in state. For each player:
- Fetches articles from NewsAPI (`tools/news_fetcher.py`)
- Embeds and stores new articles in ChromaDB (`tools/vector_store.py`) — duplicate check on article URL
- Analyzes sentiment via LLM (`tools/sentiment.py`) — returns `PlayerSentiment` + list of `ArticleSentiment`
- Fetches season stats from API-Football (`tools/stats_fetcher.py`) — uses local JSON cache, picks league by max appearances
- Scrapes market value, contract expiry, and season stats from Transfermarkt (`tools/transfermarkt.py`)

LangFuse trace: `fetch_data`

### detect_alerts

Rule-based checks — no LLM call. Fires alerts when:
- `sentiment_overall == "negative"` → negative coverage alert
- `sentiment_overall == "no_coverage"` → visibility alert
- `rating < 7.0` → below-average performance alert
- `days_until_expiry < 180` → contract expiring soon alert
- `days_until_expiry < 0` → contract expired alert

Writes alert list into `PlayerResult.alerts`.

### should_generate (conditional edge)

Returns `"generate_briefings"` if any player in state has alerts, or if a full briefing was explicitly requested. Returns `"END"` otherwise.

### generate_briefings

For each player with alerts (or all players if full run), builds a prompt with:
- Season statistics (goals, assists, appearances, rating)
- Market value and contract data
- RAG context: top 5 relevant articles retrieved from ChromaDB via `retrieve_context(player_name, k=5)`
- Sentiment summary and alert list

Model: `google/gemini-2.5-flash`

LangFuse trace: `generate_briefings` (decorated with `@observe`)

Writes briefing text into `PlayerResult.briefing`.

### human_review

Interrupt node. LangGraph pauses execution here before this node runs. The agent reviews all generated briefings in the frontend or terminal, then resumes execution. No LLM call — pure human gate.

---

## State Schema

```python
class AgentState(TypedDict):
    players: list[dict]            # input: player dicts from player store
    results: list[PlayerResult]    # output: one per player, populated by fetch_data
    pending_briefings: list[str]   # briefing texts waiting for human review
    human_approved: bool           # set to True after human_review resumes
```

`PlayerResult` fields: `name`, `club`, `articles_count`, `sentiment`, `goals`, `assists`, `appearances`, `rating`, `market_value_eur`, `contract_expires`, `days_until_expiry`, `alerts`, `briefing`

---

## How to Run

**Portfolio run — all players:**
```python
from agents.graph import app
from tools.player_store import load_players

config = {"configurable": {"thread_id": "run-001"}}

app.invoke(
    {"players": [p.__dict__ for p in load_players()], "results": [], "pending_briefings": [], "human_approved": False},
    config=config
)
```

**Single player run:**
```python
app.invoke(
    {"players": [mbappe.__dict__], "results": [], "pending_briefings": [], "human_approved": False},
    config=config
)
```

The graph is identical for both — the scope is controlled by what is passed in `players`.

---

## Human-in-the-Loop

The graph is compiled with `interrupt_before=["human_review"]`:

```python
app = graph.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["human_review"]
)
```

When execution reaches the `human_review` node, LangGraph serializes the full state to the checkpointer and pauses. The calling code receives control back and can inspect `state["pending_briefings"]`.

To resume after the agent approves:

```python
app.invoke(None, config=config)
```

Passing `None` as input tells LangGraph to resume from the checkpoint using the existing state. Execution continues from `human_review` through to `END`.

---

## Adding a Player

`transfermarkt_url` is a mandatory field. Copy it directly from the player's profile page on transfermarkt.com.

```python
from tools.player_store import add_player

add_player(
    name="Bruno Fernandes",
    club="Manchester United",
    position="Midfielder",
    transfermarkt_url="https://www.transfermarkt.com/bruno-fernandes/profil/spieler/240306"
)
```

`add_player()` automatically resolves the API-Football player ID from name + club. The Transfermarkt ID is extracted from the URL. Both are stored in the player record.

Do not guess or construct TM URLs. Copy from browser — this guarantees the correct player regardless of name variations or shared surnames.
