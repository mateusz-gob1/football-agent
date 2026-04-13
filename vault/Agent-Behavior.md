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
  (@observe LangFuse, RAG context, Gemini Flash + Claude Sonnet parallel)
  │
  ▼
critique_briefings
  (Flash Lite scores Flash and Sonnet briefings 0–9, selects winner)
  │
  ▼
should_retry ──── (both fail AND attempts < 2) ────► generate_briefings
  │
  │ (pass OR max attempts reached)
  ▼
END  (best briefing selected, results available in dashboard)
```

`should_generate` and `should_retry` are conditional edge functions — not standalone nodes.

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
- Season statistics (goals, assists, appearances, minutes)
- Market value and contract data
- RAG context: top 5 relevant articles retrieved from ChromaDB via `retrieve_context(player_name, k=5)`
- Sentiment summary and alert list

Both models run in parallel: `google/gemini-2.5-flash` (Flash) and `anthropic/claude-sonnet-4-6` (Sonnet).

LangFuse trace: `generate_briefings` (decorated with `@observe`)

Writes `briefing_flash` and `briefing_sonnet` into `PlayerResult`.

### critique_briefings

Scores both briefings using `google/gemini-2.5-flash-lite`. Three criteria, each scored 1–3:
- **ACTIONABLE** — does the briefing give the agent concrete next steps?
- **GROUNDED** — are claims backed by data (stats, articles, contract info)?
- **ALERT-AWARE** — are all detected alerts addressed?

Max score: 9/9. Pass threshold: ≥7/9. The higher-scoring briefing is selected as `PlayerResult.briefing`. Scores and feedback stored in `PlayerResult.reflection`.

### should_retry (conditional edge)

If any player has both models failing (score < 7) AND `briefing_attempts < MAX_REFLECTION_ATTEMPTS` (2): routes back to `generate_briefings` with critique feedback injected into the prompt. Otherwise routes to `"end"` → END.

---

## State Schema

```python
class AgentState(TypedDict):
    players: list[dict]          # input: player dicts from player store
    results: list[PlayerResult]  # output: one per player, populated by fetch_data
    briefing_attempts: int       # incremented each time generate_briefings runs
    pending_briefings: list[str] # formatted briefings displayed in frontend
```

`PlayerResult` fields: `name`, `club`, `articles_count`, `sentiment_overall`, `sentiment_details`, `goals`, `assists`, `appearances`, `minutes`, `age`, `rating`, `league`, `market_value_eur`, `contract_expires`, `days_until_expiry`, `value_history`, `alerts`, `briefing_flash`, `briefing_sonnet`, `briefing`, `reflection`

---

## How to Run

**Portfolio run — all players:**
```python
from agents.graph import app
from tools.player_store import load_players

config = {"configurable": {"thread_id": "run-001"}}

app.invoke(
    {"players": [p.__dict__ for p in load_players()], "results": [], "pending_briefings": [], "briefing_attempts": 0},
    config=config
)
```

**Single player run:**
```python
app.invoke(
    {"players": [player.__dict__], "results": [], "pending_briefings": [], "briefing_attempts": 0},
    config=config
)
```

The graph is identical for both — scope is controlled by what is passed in `players`.

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
