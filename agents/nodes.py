import os
from langfuse.openai import OpenAI
from langfuse import observe
from dotenv import load_dotenv

from tools.news_fetcher import fetch_player_news
from tools.sentiment import analyze_sentiment
from tools.stats_fetcher import get_player_stats
from tools.player_store import Player
from tools.vector_store import store_articles, retrieve_context
from agents.state import AgentState, PlayerResult

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL"),
)
MODEL = os.getenv("DEFAULT_MODEL", "google/gemini-2.5-flash-lite-preview-09-2025")
BRIEFING_MODEL = "google/gemini-2.5-flash"


@observe(name="fetch_data")
def fetch_data(state: AgentState) -> AgentState:
    results = []
    for p in state["players"]:
        player = Player(**p)
        print(f"  Fetching data for {player.name}...")

        articles = fetch_player_news(player.name, club=player.club)
        store_articles(player.name, articles)
        sentiment = analyze_sentiment(player.name, articles)
        stats = get_player_stats(player.api_football_id) if player.api_football_id else None

        result: PlayerResult = {
            "name": player.name,
            "club": player.club,
            "api_football_id": player.api_football_id,
            "articles_count": len(articles),
            "sentiment_overall": sentiment.overall,
            "sentiment_details": [
                {"title": a.title, "sentiment": a.sentiment, "reason": a.reason}
                for a in sentiment.articles
            ],
            "goals": stats.goals if stats else 0,
            "assists": stats.assists if stats else 0,
            "appearances": stats.appearances if stats else 0,
            "rating": stats.rating if stats else None,
            "league": stats.league if stats else "",
            "alerts": [],
            "briefing": None,
        }
        results.append(result)

    return {**state, "results": results}


def detect_alerts(state: AgentState) -> AgentState:
    updated = []
    for r in state["results"]:
        alerts = []

        if r["sentiment_overall"] == "negative":
            alerts.append(f"Negative media sentiment — {r['articles_count']} articles this week")

        if r["sentiment_overall"] == "no coverage":
            alerts.append("No media coverage in the last 7 days")

        if r["appearances"] > 0 and r["rating"] and r["rating"] < 7.0:
            alerts.append(f"Below-average rating: {r['rating']:.2f} in {r['league']}")

        updated.append({**r, "alerts": alerts})

    return {**state, "results": updated}


@observe(name="generate_briefings")
def generate_briefings(state: AgentState) -> AgentState:
    updated = []
    for r in state["results"]:
        rag_context = retrieve_context(r["name"])

        prompt = f"""You are an assistant to a football agent. Write a concise weekly briefing for the following player.

Player: {r['name']} ({r['club']})

STATISTICS (season 2024):
- League: {r['league']}
- Appearances: {r['appearances']} | Goals: {r['goals']} | Assists: {r['assists']}
- Average rating: {r['rating'] or 'N/A'}

RECENT MEDIA CONTEXT:
{rag_context}

MEDIA SUMMARY:
- Articles this week: {r['articles_count']}
- Overall sentiment: {r['sentiment_overall'].upper()}

ALERTS:
{chr(10).join(f"  - {alert}" for alert in r['alerts']) if r['alerts'] else "  None"}

Write a briefing of 3-4 sentences covering: current form, media image, and one recommended action for the agent. Be specific and professional."""

        response = client.chat.completions.create(
            model=BRIEFING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        briefing = response.choices[0].message.content.strip()
        updated.append({**r, "briefing": briefing})

    pending = []
    for r in updated:
        text = f"""
{'='*60}
PLAYER: {r['name']} ({r['club']})
{'='*60}
{r['briefing']}

Alerts: {', '.join(r['alerts']) if r['alerts'] else 'None'}
{'='*60}"""
        pending.append(text)

    return {**state, "results": updated, "pending_briefings": pending}


def human_review(state: AgentState) -> AgentState:
    # LangGraph will interrupt here — execution pauses until resumed
    print("\n" + "\n".join(state["pending_briefings"]))
    print("\n[WAITING FOR AGENT APPROVAL]")
    return state


def should_generate(state: AgentState) -> str:
    """Conditional edge: skip briefing generation if no results."""
    if not state.get("results"):
        return "end"
    return "generate"
