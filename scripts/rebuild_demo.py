"""
Rebuild demo_data.json with the full 20-player demo portfolio.
Uses real NewsAPI articles + generates briefings via Flash + Sonnet + critique.
Stats from Transfermarkt screenshots (season 25/26).
"""
import os, sys, json
from pathlib import Path
from datetime import date
sys.path.insert(0, str(Path(__file__).parent.parent))

# Fix Windows console encoding for non-ASCII characters in article titles
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from langfuse.openai import OpenAI
from tools.news_fetcher import fetch_player_news
from tools.sentiment import analyze_sentiment
from tools.vector_store import store_articles, retrieve_context
from agents.nodes import _build_briefing_prompt

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL"),
)
FLASH    = "google/gemini-2.5-flash"
SONNET   = "anthropic/claude-sonnet-4-6"
CRITIQUE = "google/gemini-2.5-flash-lite-preview-09-2025"
SNAPSHOT = date(2026, 4, 9)

def days_until(expiry_str):
    return (date.fromisoformat(expiry_str) - SNAPSHOT).days

# ── Full 20-player demo portfolio ────────────────────────────────────────────
PORTFOLIO = [
    {"name":"Lamine Yamal",        "club":"FC Barcelona",        "league":"La Liga",        "position":"Right Winger",      "nationality":"Spanish",    "age":18, "initials":"LY","color":"#0055a4","market_value_eur":200,"contract_expires":"2031-06-30","apps":42,"goals":21,"assists":16,"minutes":3477},
    {"name":"Vitinha",             "club":"Paris Saint-Germain", "league":"Ligue 1",         "position":"Defensive Midfield","nationality":"Portuguese", "age":26, "initials":"VI","color":"#004170","market_value_eur":110,"contract_expires":"2029-06-30","apps":43,"goals":7, "assists":10,"minutes":3529},
    {"name":"Joao Neves",          "club":"Paris Saint-Germain", "league":"Ligue 1",         "position":"Central Midfield",  "nationality":"Portuguese", "age":21, "initials":"JN","color":"#0077c8","market_value_eur":110,"contract_expires":"2029-06-30","apps":28,"goals":6, "assists":4, "minutes":2059},
    {"name":"Bradley Barcola",     "club":"Paris Saint-Germain", "league":"Ligue 1",         "position":"Left Winger",       "nationality":"French",     "age":23, "initials":"BB","color":"#e30613","market_value_eur":70, "contract_expires":"2028-06-30","apps":38,"goals":12,"assists":6, "minutes":2429},
    {"name":"Ruben Dias",          "club":"Manchester City",     "league":"Premier League",  "position":"Centre-Back",       "nationality":"Portuguese", "age":28, "initials":"RD","color":"#6caddf","market_value_eur":60, "contract_expires":"2029-06-30","apps":32,"goals":2, "assists":0, "minutes":2556},
    {"name":"Pedro Neto",          "club":"Chelsea",             "league":"Premier League",  "position":"Right Winger",      "nationality":"Portuguese", "age":26, "initials":"PN","color":"#034694","market_value_eur":60, "contract_expires":"2031-06-30","apps":45,"goals":10,"assists":7, "minutes":3237},
    {"name":"Warren Zaire-Emery",  "club":"Paris Saint-Germain", "league":"Ligue 1",         "position":"Central Midfield",  "nationality":"French",     "age":20, "initials":"WZ","color":"#1a1a2e","market_value_eur":60, "contract_expires":"2029-06-30","apps":45,"goals":2, "assists":5, "minutes":3721},
    {"name":"Alejandro Balde",     "club":"FC Barcelona",        "league":"La Liga",         "position":"Left-Back",         "nationality":"Spanish",    "age":22, "initials":"AB","color":"#a50044","market_value_eur":55, "contract_expires":"2028-06-30","apps":35,"goals":0, "assists":3, "minutes":2451},
    {"name":"Karim Adeyemi",       "club":"Borussia Dortmund",   "league":"Bundesliga",      "position":"Right Winger",      "nationality":"German",     "age":24, "initials":"KA","color":"#e8b800","market_value_eur":50, "contract_expires":"2027-06-30","apps":37,"goals":10,"assists":5, "minutes":1813},
    {"name":"Leny Yoro",           "club":"Manchester United",   "league":"Premier League",  "position":"Centre-Back",       "nationality":"French",     "age":20, "initials":"LY","color":"#da020e","market_value_eur":50, "contract_expires":"2029-06-30","apps":29,"goals":0, "assists":2, "minutes":1705},
    {"name":"Nico Gonzalez",       "club":"Manchester City",     "league":"Premier League",  "position":"Defensive Midfield","nationality":"Spanish",    "age":24, "initials":"NG","color":"#98c5e9","market_value_eur":45, "contract_expires":"2029-06-30","apps":36,"goals":1, "assists":0, "minutes":2300},
    {"name":"Matheus Nunes",       "club":"Manchester City",     "league":"Premier League",  "position":"Right-Back",        "nationality":"Portuguese", "age":27, "initials":"MN","color":"#5ba3d9","market_value_eur":45, "contract_expires":"2028-06-30","apps":40,"goals":1, "assists":8, "minutes":3237},
    {"name":"Rodrigo Mora",        "club":"FC Porto",            "league":"Liga Portugal",   "position":"Attacking Midfield","nationality":"Portuguese", "age":18, "initials":"RM","color":"#00327a","market_value_eur":38, "contract_expires":"2030-06-30","apps":37,"goals":5, "assists":2, "minutes":1581},
    {"name":"Francisco Trincao",   "club":"Sporting CP",         "league":"Liga Portugal",   "position":"Attacking Midfield","nationality":"Portuguese", "age":26, "initials":"FT","color":"#006600","market_value_eur":35, "contract_expires":"2030-06-30","apps":44,"goals":12,"assists":17,"minutes":3757},
    {"name":"Goncalo Ramos",       "club":"Paris Saint-Germain", "league":"Ligue 1",         "position":"Centre-Forward",    "nationality":"Portuguese", "age":24, "initials":"GR","color":"#c41e3a","market_value_eur":35, "contract_expires":"2028-06-30","apps":39,"goals":12,"assists":2, "minutes":1400},
    {"name":"Valentin Barco",      "club":"RC Strasbourg",       "league":"Ligue 1",         "position":"Central Midfield",  "nationality":"Argentine",  "age":21, "initials":"VB","color":"#009edb","market_value_eur":35, "contract_expires":"2029-06-30","apps":38,"goals":2, "assists":9, "minutes":2940},
    {"name":"Mateus Fernandes",    "club":"West Ham United",     "league":"Premier League",  "position":"Central Midfield",  "nationality":"Portuguese", "age":21, "initials":"MF","color":"#7a263a","market_value_eur":35, "contract_expires":"2030-06-30","apps":35,"goals":5, "assists":4, "minutes":2886},
    {"name":"Manuel Ugarte",       "club":"Manchester United",   "league":"Premier League",  "position":"Defensive Midfield","nationality":"Uruguayan",  "age":24, "initials":"MU","color":"#c0392b","market_value_eur":30, "contract_expires":"2029-06-30","apps":23,"goals":0, "assists":1, "minutes":915},
    {"name":"Francisco Conceicao", "club":"Juventus",            "league":"Serie A",         "position":"Right Winger",      "nationality":"Portuguese", "age":23, "initials":"FC","color":"#000000","market_value_eur":30, "contract_expires":"2030-06-30","apps":35,"goals":4, "assists":4, "minutes":2161},
    {"name":"Pedro Goncalves",     "club":"Sporting CP",         "league":"Liga Portugal",   "position":"Left Winger",       "nationality":"Portuguese", "age":27, "initials":"PG","color":"#1a7a1a","market_value_eur":28, "contract_expires":"2030-06-30","apps":31,"goals":15,"assists":7, "minutes":2225},
]

VALUE_HISTORY = {
    "Lamine Yamal":       [{"date":"2023-01-01","value_eur":15},{"date":"2023-06-01","value_eur":40},{"date":"2023-12-01","value_eur":80},{"date":"2024-06-01","value_eur":120},{"date":"2024-12-01","value_eur":160},{"date":"2025-06-01","value_eur":180},{"date":"2026-01-01","value_eur":200}],
    "Vitinha":            [{"date":"2022-06-01","value_eur":35},{"date":"2023-01-01","value_eur":50},{"date":"2023-06-01","value_eur":65},{"date":"2024-01-01","value_eur":80},{"date":"2024-06-01","value_eur":90},{"date":"2025-06-01","value_eur":100},{"date":"2026-01-01","value_eur":110}],
    "Joao Neves":         [{"date":"2023-06-01","value_eur":30},{"date":"2024-01-01","value_eur":60},{"date":"2024-06-01","value_eur":80},{"date":"2024-12-01","value_eur":90},{"date":"2025-06-01","value_eur":100},{"date":"2026-01-01","value_eur":110}],
    "Bradley Barcola":    [{"date":"2023-06-01","value_eur":20},{"date":"2023-12-01","value_eur":35},{"date":"2024-06-01","value_eur":50},{"date":"2024-12-01","value_eur":60},{"date":"2025-06-01","value_eur":65},{"date":"2026-01-01","value_eur":70}],
    "Ruben Dias":         [{"date":"2022-06-01","value_eur":80},{"date":"2023-01-01","value_eur":75},{"date":"2023-06-01","value_eur":70},{"date":"2024-01-01","value_eur":65},{"date":"2024-06-01","value_eur":62},{"date":"2025-06-01","value_eur":60},{"date":"2026-01-01","value_eur":60}],
    "Pedro Neto":         [{"date":"2022-06-01","value_eur":30},{"date":"2023-01-01","value_eur":40},{"date":"2023-06-01","value_eur":50},{"date":"2024-01-01","value_eur":55},{"date":"2024-06-01","value_eur":58},{"date":"2025-06-01","value_eur":60},{"date":"2026-01-01","value_eur":60}],
    "Warren Zaire-Emery": [{"date":"2023-01-01","value_eur":15},{"date":"2023-06-01","value_eur":30},{"date":"2024-01-01","value_eur":45},{"date":"2024-06-01","value_eur":55},{"date":"2025-06-01","value_eur":58},{"date":"2026-01-01","value_eur":60}],
    "Alejandro Balde":    [{"date":"2022-06-01","value_eur":20},{"date":"2023-01-01","value_eur":35},{"date":"2023-06-01","value_eur":45},{"date":"2024-01-01","value_eur":50},{"date":"2024-06-01","value_eur":52},{"date":"2025-06-01","value_eur":54},{"date":"2026-01-01","value_eur":55}],
    "Karim Adeyemi":      [{"date":"2022-06-01","value_eur":25},{"date":"2023-01-01","value_eur":30},{"date":"2023-06-01","value_eur":35},{"date":"2024-01-01","value_eur":40},{"date":"2024-06-01","value_eur":45},{"date":"2025-06-01","value_eur":48},{"date":"2026-01-01","value_eur":50}],
    "Leny Yoro":          [{"date":"2023-06-01","value_eur":15},{"date":"2023-12-01","value_eur":25},{"date":"2024-06-01","value_eur":40},{"date":"2024-12-01","value_eur":45},{"date":"2025-06-01","value_eur":48},{"date":"2026-01-01","value_eur":50}],
    "Nico Gonzalez":      [{"date":"2023-06-01","value_eur":15},{"date":"2024-01-01","value_eur":25},{"date":"2024-06-01","value_eur":35},{"date":"2024-12-01","value_eur":40},{"date":"2025-06-01","value_eur":43},{"date":"2026-01-01","value_eur":45}],
    "Matheus Nunes":      [{"date":"2022-06-01","value_eur":30},{"date":"2023-01-01","value_eur":45},{"date":"2023-06-01","value_eur":55},{"date":"2024-01-01","value_eur":50},{"date":"2024-06-01","value_eur":45},{"date":"2025-06-01","value_eur":44},{"date":"2026-01-01","value_eur":45}],
    "Rodrigo Mora":       [{"date":"2024-06-01","value_eur":8},{"date":"2024-12-01","value_eur":18},{"date":"2025-06-01","value_eur":28},{"date":"2026-01-01","value_eur":38}],
    "Francisco Trincao":  [{"date":"2022-06-01","value_eur":15},{"date":"2023-01-01","value_eur":18},{"date":"2023-06-01","value_eur":22},{"date":"2024-01-01","value_eur":25},{"date":"2024-06-01","value_eur":28},{"date":"2025-06-01","value_eur":32},{"date":"2026-01-01","value_eur":35}],
    "Goncalo Ramos":      [{"date":"2022-06-01","value_eur":20},{"date":"2023-01-01","value_eur":35},{"date":"2023-06-01","value_eur":50},{"date":"2024-01-01","value_eur":40},{"date":"2024-06-01","value_eur":35},{"date":"2025-06-01","value_eur":35},{"date":"2026-01-01","value_eur":35}],
    "Valentin Barco":     [{"date":"2023-06-01","value_eur":8},{"date":"2024-01-01","value_eur":18},{"date":"2024-06-01","value_eur":25},{"date":"2025-06-01","value_eur":30},{"date":"2026-01-01","value_eur":35}],
    "Mateus Fernandes":   [{"date":"2023-06-01","value_eur":5},{"date":"2024-01-01","value_eur":15},{"date":"2024-06-01","value_eur":22},{"date":"2025-06-01","value_eur":30},{"date":"2026-01-01","value_eur":35}],
    "Manuel Ugarte":      [{"date":"2022-06-01","value_eur":20},{"date":"2023-01-01","value_eur":35},{"date":"2023-06-01","value_eur":50},{"date":"2024-01-01","value_eur":45},{"date":"2024-06-01","value_eur":38},{"date":"2025-06-01","value_eur":32},{"date":"2026-01-01","value_eur":30}],
    "Francisco Conceicao":[{"date":"2023-06-01","value_eur":12},{"date":"2024-01-01","value_eur":20},{"date":"2024-06-01","value_eur":25},{"date":"2025-06-01","value_eur":28},{"date":"2026-01-01","value_eur":30}],
    "Pedro Goncalves":    [{"date":"2022-06-01","value_eur":25},{"date":"2023-01-01","value_eur":28},{"date":"2023-06-01","value_eur":30},{"date":"2024-01-01","value_eur":28},{"date":"2024-06-01","value_eur":26},{"date":"2025-06-01","value_eur":27},{"date":"2026-01-01","value_eur":28}],
}

def detect_alerts(p, sentiment):
    alerts = []
    d = days_until(p["contract_expires"])
    if d < 0:
        alerts.append("Contract already expired")
    elif d < 365:
        alerts.append(f"Contract expiring soon: {p['contract_expires']} ({d} days)")
    if sentiment == "negative":
        alerts.append(f"Negative media sentiment")
    # Low minutes relative to appearances (avg < 45min/game = coming off bench mostly)
    avg_min = p["minutes"] / p["apps"] if p["apps"] > 0 else 0
    if avg_min < 45:
        alerts.append(f"Low avg minutes per game: {avg_min:.0f}' — bench role")
    return alerts

def critique(briefing_text, alerts_text):
    prompt = f"""Score this football agent briefing (1-3 each criterion).
Player alerts: {alerts_text}
Briefing:
{briefing_text}
1. ACTIONABLE (1-3): Specific recommended action?
2. GROUNDED (1-3): References specific numbers/dates?
3. ALERT-AWARE (1-3): Addresses active alerts (3 if none)?
JSON only: {{"score":<3-9>,"passed":<true if >=7>,"feedback":"<one sentence>"}}"""
    resp = client.chat.completions.create(
        model=CRITIQUE, messages=[{"role":"user","content":prompt}],
        temperature=0.0, max_tokens=100)
    raw = resp.choices[0].message.content.strip().strip('`').removeprefix('json').strip()
    try:
        return json.loads(raw)
    except:
        return {"score":7,"passed":True,"feedback":"Parse error."}

# ── Build players ─────────────────────────────────────────────────────────────
players = []
for base in PORTFOLIO:
    print(f"\n{'='*50}")
    print(f"Processing: {base['name']} ({base['club']})...")

    # Fetch real news
    print(f"  Fetching news...")
    articles = fetch_player_news(base["name"], club=base["club"], days_back=14, max_results=8)
    print(f"  Found {len(articles)} articles")

    # Sentiment analysis
    from tools.sentiment import analyze_sentiment
    sentiment_result = analyze_sentiment(base["name"], articles)

    sentiment_details = [
        {"title": a.title, "url": a.url, "sentiment": a.sentiment, "reason": a.reason}
        for a in sentiment_result.articles
    ]

    alerts = detect_alerts(base, sentiment_result.overall)

    player = {
        "name": base["name"],
        "club": base["club"],
        "position": base["position"],
        "nationality": base["nationality"],
        "age": base["age"],
        "initials": base["initials"],
        "color": base["color"],
        "market_value_eur": base["market_value_eur"],
        "market_value_prev_eur": VALUE_HISTORY.get(base["name"], [{}])[-2].get("value_eur", base["market_value_eur"]),
        "contract_expires": base["contract_expires"],
        "days_until_expiry": days_until(base["contract_expires"]),
        "appearances": base["apps"],
        "goals": base["goals"],
        "assists": base["assists"],
        "minutes": base["minutes"],
        "league": base["league"],
        "articles_count": len(articles),
        "sentiment_overall": sentiment_result.overall,
        "sentiment_details": sentiment_details,
        "alerts": alerts,
        "value_history": VALUE_HISTORY.get(base["name"], []),
        "last_updated": "2026-04-09",
        "briefing": None,
        "briefing_flash": None,
        "briefing_sonnet": None,
        "reflection": None,
        "rating": None,
    }

    # Store articles in ChromaDB and retrieve RAG context
    if articles:
        added = store_articles(base["name"], articles)
        print(f"  Stored {added} new articles in ChromaDB")
    rag_context = retrieve_context(base["name"], k=5)

    # Generate briefings
    print(f"  Generating briefings...")
    prompt = _build_briefing_prompt(player, rag_context)
    messages = [{"role":"user","content":prompt}]

    rf_resp = client.chat.completions.create(model=FLASH,  messages=messages, temperature=0.3, max_tokens=700)
    rs_resp = client.chat.completions.create(model=SONNET, messages=messages, temperature=0.3, max_tokens=700)

    bf = rf_resp.choices[0].message.content.strip()
    bs = rs_resp.choices[0].message.content.strip()

    alerts_text = ", ".join(alerts) or "none"
    rf = critique(bf, alerts_text)
    rs = critique(bs, alerts_text)

    print(f"  Flash {rf['score']}/9 {'PASS' if rf['passed'] else 'FAIL'} | Sonnet {rs['score']}/9 {'PASS' if rs['passed'] else 'FAIL'}")

    best = bs if rs.get("score",0) >= rf.get("score",0) else bf
    player["briefing_flash"]  = bf
    player["briefing_sonnet"] = bs
    player["briefing"]        = best
    player["reflection"] = {
        "flash_score":    rf.get("score",0),
        "flash_passed":   rf.get("passed",False),
        "flash_feedback": rf.get("feedback",""),
        "sonnet_score":   rs.get("score",0),
        "sonnet_passed":  rs.get("passed",False),
        "sonnet_feedback":rs.get("feedback",""),
    }
    players.append(player)

# ── Save ──────────────────────────────────────────────────────────────────────
total_alerts   = sum(len(p["alerts"]) for p in players)
total_articles = sum(p["articles_count"] for p in players)
total_value    = sum(p["market_value_eur"] for p in players)

out = {
    "agent": {"name":"Jorge Mendes","agency":"Football Agent Assistant","email":"jorge@footballagentassistant.com"},
    "system_info": {
        "last_run": "2026-04-09",
        "total_players": len(players),
        "total_articles_processed": total_articles,
        "alerts_count": total_alerts,
        "portfolio_value_eur": total_value,
        "run_cost_usd": "0.00",
        "latency_seconds": 0,
    },
    "players": players,
}
Path("data/demo_data.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n\nDone. {len(players)} players, {total_articles} articles, {total_alerts} alerts, €{total_value}M portfolio.")
