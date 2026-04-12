from typing import TypedDict


class PlayerResult(TypedDict):
    name: str
    club: str
    api_football_id: int | None
    # news
    articles_count: int
    sentiment_overall: str       # positive | negative | neutral | mixed | no coverage
    sentiment_details: list[dict]
    # stats
    goals: int
    assists: int
    appearances: int
    minutes: int
    age: int
    rating: float | None
    league: str
    # transfermarkt
    market_value_eur: float | None
    contract_expires: str | None
    days_until_expiry: int | None
    # weekly snapshots from SQLite — used for value trend chart
    value_history: list[dict]
    # alerts
    alerts: list[str]
    # briefings — two models compared
    briefing_flash: str | None           # gemini-2.5-flash output
    briefing_sonnet: str | None          # claude-sonnet-4-6 output
    briefing: str | None                 # selected best (winner after reflection)
    # reflection output per player
    reflection: dict | None              # {flash_score, flash_passed, flash_feedback,
                                         #  sonnet_score, sonnet_passed, sonnet_feedback}


class AgentState(TypedDict):
    # input
    players: list[dict]                  # list of Player dicts from player_store
    # accumulated during run
    results: list[PlayerResult]          # one entry per player after processing
    # reflection loop control
    briefing_attempts: int               # incremented each time generate_briefings runs
    # briefings ready for async review in the dashboard
    pending_briefings: list[str]         # formatted briefings displayed in frontend
