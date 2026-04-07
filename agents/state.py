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
    rating: float | None
    league: str
    # transfermarkt
    market_value_eur: float | None
    contract_expires: str | None
    days_until_expiry: int | None
    # alerts
    alerts: list[str]
    # briefing
    briefing: str | None


class AgentState(TypedDict):
    # input
    players: list[dict]                  # list of Player dicts from player_store
    # accumulated during run
    results: list[PlayerResult]          # one entry per player after processing
    # human-in-the-loop
    pending_briefings: list[str]         # formatted briefings waiting for review
    human_approved: bool                 # set to True when agent approves
