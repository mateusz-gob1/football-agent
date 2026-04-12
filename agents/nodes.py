import os
import json
from langfuse.openai import OpenAI
from langfuse import observe
from dotenv import load_dotenv

from tools.news_fetcher import fetch_player_news
from tools.sentiment import analyze_sentiment
from tools.stats_fetcher import get_player_stats
from tools.transfermarkt import get_player_market_data
from tools.player_store import Player
from tools.vector_store import store_articles, retrieve_context
from tools.history_store import save_snapshot, get_snapshots
from agents.state import AgentState, PlayerResult

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL"),
)
MODEL = os.getenv("DEFAULT_MODEL", "google/gemini-2.5-flash-lite-preview-09-2025")
BRIEFING_MODEL_FLASH  = "google/gemini-2.5-flash"
BRIEFING_MODEL_SONNET = "anthropic/claude-sonnet-4-6"
CRITIQUE_MODEL        = "google/gemini-2.5-flash-lite-preview-09-2025"
MAX_REFLECTION_ATTEMPTS = 2


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
        market = get_player_market_data(player.transfermarkt_url, player.name) if player.transfermarkt_url else None

        if market:
            save_snapshot(
                player.name,
                market.market_value_eur,
                market.contract_expires,
                market.days_until_expiry,
            )

        result: PlayerResult = {
            "name": player.name,
            "club": player.club,
            "api_football_id": player.api_football_id,
            "articles_count": len(articles),
            "sentiment_overall": sentiment.overall,
            "sentiment_details": [
                {"title": a.title, "url": a.url, "sentiment": a.sentiment, "reason": a.reason}
                for a in sentiment.articles
            ],
            "goals": stats.goals if stats else 0,
            "assists": stats.assists if stats else 0,
            "appearances": stats.appearances if stats else 0,
            "rating": stats.rating if stats else None,
            "league": stats.league if stats else "",
            "market_value_eur": market.market_value_eur if market else None,
            "contract_expires": market.contract_expires if market else None,
            "days_until_expiry": market.days_until_expiry if market else None,
            "value_history": get_snapshots(player.name),
            "alerts": [],
            "briefing": None,
        }
        results.append(result)

    return {**state, "results": results}


SIGNAL_LABELS = {
    "transfer_rumor":       "Transfer rumor",
    "injury":               "Injury concern",
    "dispute":              "Internal dispute",
    "contract_negotiation": "Contract talks",
    "off_field_issue":      "Off-field issue",
}


@observe(name="detect_signals")
def detect_signals(state: AgentState) -> AgentState:
    """LLM-powered signal detection — reads article headlines and flags non-obvious intelligence signals."""
    updated = []
    for r in state["results"]:
        articles = r.get("sentiment_details") or []
        if not articles:
            updated.append(r)
            continue

        headlines = "\n".join(f"- {a['title']}" for a in articles if a.get("title"))

        prompt = f"""You analyze media coverage of football player {r['name']} ({r['club']}).

Headlines this week:
{headlines}

Identify signals that a football agent would want to know about:
- transfer_rumor: player linked to a move to another club
- injury: player injured, ill, or struggling physically
- dispute: conflict with manager, club, or teammates
- contract_negotiation: contract renewal or talks mentioned
- off_field_issue: disciplinary problem, scandal, or controversy

Return a JSON array. Only include signals clearly supported by the headlines.
For each signal: {{"signal": "...", "confidence": "high|medium", "evidence": "one sentence, max 12 words"}}
If no signals found return: []
JSON only, no markdown."""

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            content = response.choices[0].message.content or "[]"
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            signals = json.loads(content)
            if not isinstance(signals, list):
                signals = []
        except Exception:
            signals = []

        new_alerts = list(r.get("alerts") or [])
        for s in signals:
            if not isinstance(s, dict):
                continue
            label = SIGNAL_LABELS.get(s.get("signal", ""), s.get("signal", "Signal"))
            evidence = s.get("evidence", "")
            confidence = s.get("confidence", "medium")
            prefix = "[!]" if confidence == "high" else "[?]"
            new_alerts.append(f"{prefix} {label} — {evidence}")

        updated.append({**r, "alerts": new_alerts})

    return {**state, "results": updated}


def detect_alerts(state: AgentState) -> AgentState:
    """Rule-based alert detection — appends to alerts already set by detect_signals."""
    updated = []
    for r in state["results"]:
        alerts = list(r.get("alerts") or [])  # preserve LLM signals from previous node

        if r["sentiment_overall"] == "negative":
            alerts.append(f"Negative media sentiment — {r['articles_count']} articles this week")

        if r["sentiment_overall"] == "no coverage":
            alerts.append("No media coverage in the last 7 days")

        if r["appearances"] > 0 and r["rating"] and r["rating"] < 7.0:
            alerts.append(f"Below-average rating: {r['rating']:.2f} in {r['league']}")

        if r.get("days_until_expiry") is not None:
            if r["days_until_expiry"] < 0:
                alerts.append("Contract already expired")
            elif r["days_until_expiry"] < 180:
                alerts.append(f"Contract expiring soon: {r['contract_expires']} ({r['days_until_expiry']} days)")

        updated.append({**r, "alerts": alerts})

    return {**state, "results": updated}


def _build_briefing_prompt(r: dict, rag_context: str, critique_feedback: str | None = None) -> str:
    market_line   = f"€{r['market_value_eur']}M" if r.get("market_value_eur") else "N/A"
    contract_line = f"{r['contract_expires']} ({r['days_until_expiry']} days)" if r.get("contract_expires") else "N/A"
    alerts_text   = "\n".join(f"  - {a}" for a in r["alerts"]) if r["alerts"] else "  None"

    # Build article sources list with URLs
    sources_text = ""
    for art in (r.get("sentiment_details") or []):
        url_part = f" — {art['url']}" if art.get("url") else ""
        sources_text += f"  [{art['sentiment'].upper()}] {art['title']}{url_part}\n"
    if not sources_text:
        sources_text = "  No articles this week\n"

    feedback_section = ""
    if critique_feedback:
        feedback_section = f"""
PREVIOUS ATTEMPT FEEDBACK (improve on this):
{critique_feedback}
"""

    return f"""You are an intelligence analyst assisting a professional football agent. Write a detailed weekly intelligence brief for the following player.

Player: {r['name']} ({r['club']})

PLAYER PROFILE:
- Age: {r.get('age', 'N/A')} years old

SEASON STATISTICS (25/26):
- League: {r['league']}
- Appearances: {r['appearances']} | Goals: {r['goals']} | Assists: {r['assists']} | Minutes: {r.get('minutes', 'N/A')}'

MARKET DATA:
- Current market value: {market_line}
- Contract expires: {contract_line}

RECENT MEDIA CONTEXT (RAG retrieval):
{rag_context}

MEDIA ARTICLES THIS WEEK ({r['articles_count']} total, overall sentiment: {r['sentiment_overall'].upper()}):
{sources_text}
ACTIVE ALERTS:
{alerts_text}
{feedback_section}
Output the brief with NO title, NO header, NO player name, NO date line, NO classification label, NO preamble of any kind. Start the response immediately with the bold section header **FORM & PERFORMANCE** and nothing before it.

Use EXACTLY this four-section format every time:

**FORM & PERFORMANCE**
[2-3 sentences on current form with specific numbers — appearances, goals, assists, rating if available.]

**MEDIA INTELLIGENCE**
[2-3 sentences on key narratives from the articles listed above. Reference specific article titles. Flag any negative or risk coverage.]

**MARKET & CONTRACT**
[2-3 sentences on market value (€XM), contract expiry date, transfer window implications. Reference actual figures.]

**RECOMMENDED ACTIONS**
1. [Most urgent action — name a specific person, club, or hard deadline]
2. [Second priority]
3. [Third if relevant, else omit]

Rules:
- No markdown headers (#, ##), no horizontal rules (---), no metadata lines
- Reference actual numbers and dates from the data above — no generic statements
- If there are active alerts, at least one action must directly address them
- Tone: direct, professional, written for a sports agent"""


@observe(name="generate_briefings")
def generate_briefings(state: AgentState) -> AgentState:
    attempt = state.get("briefing_attempts", 0)
    updated = []

    for r in state["results"]:
        rag_context = retrieve_context(r["name"])

        # On retry: extract previous feedback for this player from reflection results
        prev_feedback = None
        if attempt > 0 and r.get("reflection"):
            ref = r["reflection"]
            # Use feedback from whichever model scored lower, or combine both
            feedbacks = []
            if not ref.get("flash_passed"):
                feedbacks.append(f"Flash: {ref.get('flash_feedback', '')}")
            if not ref.get("sonnet_passed"):
                feedbacks.append(f"Sonnet: {ref.get('sonnet_feedback', '')}")
            if feedbacks:
                prev_feedback = " | ".join(feedbacks)

        prompt = _build_briefing_prompt(r, rag_context, prev_feedback)
        messages = [{"role": "user", "content": prompt}]

        # Generate with both models
        resp_flash = client.chat.completions.create(
            model=BRIEFING_MODEL_FLASH,
            messages=messages,
            temperature=0.3,
            max_tokens=700,
        )
        resp_sonnet = client.chat.completions.create(
            model=BRIEFING_MODEL_SONNET,
            messages=messages,
            temperature=0.3,
            max_tokens=700,
        )

        briefing_flash  = resp_flash.choices[0].message.content.strip()
        briefing_sonnet = resp_sonnet.choices[0].message.content.strip()

        updated.append({
            **r,
            "briefing_flash":  briefing_flash,
            "briefing_sonnet": briefing_sonnet,
            "briefing":        briefing_sonnet,   # default to sonnet; overridden by critique
            "reflection":      None,              # will be filled by critique_briefings
        })

    return {**state, "results": updated, "briefing_attempts": attempt + 1}


@observe(name="critique_briefings")
def critique_briefings(state: AgentState) -> AgentState:
    """
    Evaluate both briefings per player using a lightweight model.
    Scores on three criteria (1-3 each):
      1. ACTIONABLE — specific recommended action for the agent
      2. GROUNDED   — references actual data (value, contract date, stats)
      3. ALERT-AWARE — addresses active alerts (if any)
    Pass threshold: total >= 7 out of 9.
    """
    import json as _json

    updated = []
    for r in state["results"]:
        alerts_text = ", ".join(r["alerts"]) if r["alerts"] else "none"

        def _critique(briefing_text: str) -> dict:
            prompt = f"""Score this football agent briefing on three criteria (1-3 each).

Player alerts: {alerts_text}

Briefing:
{briefing_text}

Criteria:
1. ACTIONABLE (1-3): Contains a specific recommended action tied to this player's situation?
2. GROUNDED (1-3): References specific numbers/dates from the data (not generic statements)?
3. ALERT-AWARE (1-3): Addresses active alerts if any exist (score 3 if no alerts)?

Respond with JSON only, no explanation:
{{"score": <sum 3-9>, "passed": <true if score >= 7>, "feedback": "<one sentence on biggest weakness>"}}"""

            resp = client.chat.completions.create(
                model=CRITIQUE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=100,
            )
            raw = resp.choices[0].message.content.strip()
            try:
                # Strip markdown code fences if present
                raw = raw.strip("`").removeprefix("json").strip()
                return _json.loads(raw)
            except Exception:
                return {"score": 5, "passed": False, "feedback": "Could not parse critique response."}

        flash_result  = _critique(r.get("briefing_flash", ""))
        sonnet_result = _critique(r.get("briefing_sonnet", ""))

        reflection = {
            "flash_score":    flash_result.get("score", 0),
            "flash_passed":   flash_result.get("passed", False),
            "flash_feedback": flash_result.get("feedback", ""),
            "sonnet_score":   sonnet_result.get("score", 0),
            "sonnet_passed":  sonnet_result.get("passed", False),
            "sonnet_feedback": sonnet_result.get("feedback", ""),
        }

        # Select best briefing as the primary
        if sonnet_result.get("passed"):
            best = r.get("briefing_sonnet", "")
        elif flash_result.get("passed"):
            best = r.get("briefing_flash", "")
        else:
            # Neither passed — pick higher score
            best = (
                r.get("briefing_sonnet", "")
                if sonnet_result.get("score", 0) >= flash_result.get("score", 0)
                else r.get("briefing_flash", "")
            )

        updated.append({**r, "reflection": reflection, "briefing": best})

    # Build pending_briefings for human_review display
    pending = []
    for r in updated:
        ref = r.get("reflection") or {}
        text = f"""
{'='*60}
PLAYER: {r['name']} ({r['club']})
{'='*60}
[Gemini Flash  score {ref.get('flash_score', '?')}/9{' PASS' if ref.get('flash_passed') else ' FAIL'}]
{r.get('briefing_flash', 'N/A')}

[Claude Sonnet  score {ref.get('sonnet_score', '?')}/9{' PASS' if ref.get('sonnet_passed') else ' FAIL'}]
{r.get('briefing_sonnet', 'N/A')}

SELECTED: {'Claude Sonnet' if r.get('briefing') == r.get('briefing_sonnet') else 'Gemini Flash'}
Alerts: {', '.join(r['alerts']) if r['alerts'] else 'None'}
{'='*60}"""
        pending.append(text)

    return {**state, "results": updated, "pending_briefings": pending}


def should_retry(state: AgentState) -> str:
    """
    Conditional edge after critique_briefings.
    Retry generation if any player failed both models AND we haven't hit the attempt limit.
    """
    if state.get("briefing_attempts", 0) >= MAX_REFLECTION_ATTEMPTS:
        return "human_review"

    for r in state["results"]:
        ref = r.get("reflection", {}) or {}
        if not ref.get("flash_passed") and not ref.get("sonnet_passed"):
            return "generate_briefings"

    return "human_review"


def should_generate(state: AgentState) -> str:
    """Conditional edge: skip briefing generation if no results."""
    if not state.get("results"):
        return "end"
    return "generate"
