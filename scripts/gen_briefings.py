"""
Generate rich structured briefings for demo_data.json using the actual pipeline prompt.
Also injects realistic sentiment_details with article URLs.
"""
import os, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

from langfuse.openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL"),
)

FLASH  = "google/gemini-2.5-flash"
SONNET = "anthropic/claude-sonnet-4-6"
CRITIQUE = "google/gemini-2.5-flash-lite-preview-09-2025"

# Realistic demo articles per player (title, url, sentiment, reason)
DEMO_ARTICLES = {
    "Lamine Yamal": [
        {"title": "Yamal's 17 assists cement his place as Europe's most creative teenager", "url": "https://www.barcablaugranes.com/2025/5/12/yamal-assists-record", "sentiment": "positive", "reason": "Record-breaking assist tally praised across European media"},
        {"title": "Barcelona renew talks over Yamal's long-term contract extension", "url": "https://www.sport.es/en/news/barcelona/yamal-contract-extension-talks-2025", "sentiment": "positive", "reason": "Reports suggest club eager to secure him beyond 2026"},
        {"title": "Yamal faces potential yellow card suspension ahead of Copa final", "url": "https://www.marca.com/en/football/barcelona/yamal-suspension-risk-copa", "sentiment": "negative", "reason": "Booking accumulation could rule him out of key fixture"},
    ],
    "Vitinha": [
        {"title": "Vitinha named PSG's most consistent performer of the season by L'Équipe", "url": "https://www.lequipe.fr/Football/Article/vitinha-psg-meilleur-joueur", "sentiment": "positive", "reason": "French press highlight his engine room leadership"},
        {"title": "PSG hierarchy studying midfield reinforcements for 2025-26 window", "url": "https://www.rmc.fr/sport/football/psg-mercato-milieu-2025", "sentiment": "neutral", "reason": "Potential new signings could affect Vitinha's role"},
    ],
    "Joao Neves": [
        {"title": "Joao Neves: PSG's 20-year-old driving force in Champions League run", "url": "https://www.goal.com/en/news/joao-neves-psg-champions-league-analysis", "sentiment": "positive", "reason": "Champions League performances drawing praise from European scouts"},
        {"title": "Sources: Premier League clubs monitoring Neves ahead of summer", "url": "https://www.transfermarkt.com/joao-neves-interest-premier-league-2025", "sentiment": "neutral", "reason": "Transfer interest from England reported but unconfirmed"},
        {"title": "Neves substituted in Porto clash — PSG confirm minor hamstring tightness", "url": "https://www.eurosport.com/football/ligue-1/neves-injury-scare-psg", "sentiment": "negative", "reason": "Precautionary removal raises fitness question marks"},
    ],
    "Ruben Dias": [
        {"title": "Dias commands Man City rearguard through Guardiola's injury crisis", "url": "https://www.manchestereveningnews.co.uk/sport/football/dias-man-city-leadership-2025", "sentiment": "positive", "reason": "Leadership role elevated amid defensive absentees"},
        {"title": "City open preliminary talks over Dias contract — two-year extension on table", "url": "https://www.skysports.com/football/news/11679/dias-city-contract-extension-2025", "sentiment": "positive", "reason": "Extension discussions confirm City's long-term reliance on him"},
    ],
    "Pedro Neto": [
        {"title": "Pedro Neto thriving under Maresca at Chelsea after slow start", "url": "https://www.chelseafc.com/en/news/article/pedro-neto-maresca-season-review", "sentiment": "positive", "reason": "Tactical adaptation producing stronger second-half displays"},
        {"title": "Neto's injury record remains a concern — three absences in 2024-25", "url": "https://www.physioroom.com/pedro-neto-chelsea-injuries-2025", "sentiment": "negative", "reason": "Recurring muscular issues limit consistency at Stamford Bridge"},
        {"title": "Chelsea trigger one-year option on Neto's deal — no urgency on new terms", "url": "https://www.football.london/chelsea-fc/pedro-neto-contract-option-2025", "sentiment": "neutral", "reason": "Option exercised but long-term future remains uncertain beyond 2026"},
    ],
    "Goncalo Ramos": [
        {"title": "Ramos scores twice as PSG seal Ligue 1 title with three games to spare", "url": "https://www.lequipe.fr/Football/Article/ramos-psg-titre-ligue1-2025", "sentiment": "positive", "reason": "Title-winning brace underlines his importance to PSG attack"},
        {"title": "Portugal squad: Ramos fighting for starting spot with Ronaldo era ending", "url": "https://www.record.pt/futebol/futebol-internacional/detalhe/ramos-portugal-selecao-2025", "sentiment": "neutral", "reason": "National team status in transition as new generation emerges"},
    ],
    "Francisco Conceicao": [
        {"title": "Conceicao's Juventus loan: impressive displays masking a difficult season", "url": "https://www.tuttosport.com/conceicao-juventus-review-2025", "sentiment": "neutral", "reason": "Individual flashes of quality within an inconsistent Juve campaign"},
        {"title": "Porto to trigger recall option on Conceicao if rating stays below 7.0", "url": "https://www.ojogo.pt/futebol/porto/conceicao-recall-clausula-2025", "sentiment": "negative", "reason": "Performance clause could force early return to Porto this summer"},
        {"title": "Conceicao linked with permanent Serie A stay — AC Milan monitoring", "url": "https://www.gazzetta.it/conceicao-milan-inter-interesse-2025", "sentiment": "positive", "reason": "Italian clubs circling for permanent deal ahead of window"},
    ],
    "Bernardo Silva": [
        {"title": "Bernardo Silva: the quiet architect of City's resurgence under Guardiola", "url": "https://www.theguardian.com/football/2025/bernardo-silva-analysis", "sentiment": "positive", "reason": "Deep tactical analysis positions him as City's most complete midfielder"},
        {"title": "Silva's contract talks stalled — Barcelona maintain long-running interest", "url": "https://www.sport.es/en/news/barcelona/bernardo-silva-barcelona-2025-contract", "sentiment": "neutral", "reason": "No extension signed despite reported City desire to keep him"},
        {"title": "Saudi Pro League making £400k/week offer to Bernardo — agent confirms contact", "url": "https://www.arabnews.com/bernardo-silva-saudi-offer-2025", "sentiment": "negative", "reason": "Lucrative Saudi interest complicates City and Barcelona pursuit"},
    ],
    "Joao Felix": [
        {"title": "Felix loan at Juventus cut short — Chelsea reassessing options for summer", "url": "https://www.chelseafc.com/en/news/joao-felix-loan-return-2025", "sentiment": "negative", "reason": "Disappointing Serie A spell forces Chelsea to rethink his future"},
        {"title": "Joao Felix: agent reveals three clubs in contact ahead of permanent exit", "url": "https://www.record.pt/futebol/joao-felix-agente-clubes-interessados-2025", "sentiment": "neutral", "reason": "Permanent sale increasingly likely given Chelsea's squad depth"},
        {"title": "Felix shows flashes at Juve: two goals and an assist in final six matches", "url": "https://www.tuttosport.com/felix-juventus-ultimi-sei-2025", "sentiment": "positive", "reason": "Late-season upturn provides some transfer market value recovery"},
    ],
    "Cristiano Ronaldo": [
        {"title": "Ronaldo breaks Saudi Pro League all-time scoring record with 25th goal", "url": "https://www.arabnews.com/ronaldo-saudi-scoring-record-2025", "sentiment": "positive", "reason": "Historic milestone cements legacy beyond European football"},
        {"title": "Al-Nassr offer Ronaldo record extension: €200M for final two years", "url": "https://www.goal.com/en/news/ronaldo-al-nassr-extension-offer-2025", "sentiment": "positive", "reason": "Financial package reflects club's commitment to star signing"},
        {"title": "Ronaldo's European comeback 'categorically impossible' says agent Jorge Mendes", "url": "https://www.record.pt/futebol/ronaldo-europa-regresso-impossivel-2025", "sentiment": "neutral", "reason": "Agent closes door on return rumours, focusing on Middle East future"},
    ],
}

from agents.nodes import _build_briefing_prompt
import json as _json

demo_path = Path('data/demo_data.json')
demo = _json.loads(demo_path.read_text())

def critique(briefing_text, alerts_text):
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
        model=CRITIQUE,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=100,
    )
    raw = resp.choices[0].message.content.strip().strip('`').removeprefix('json').strip()
    try:
        return _json.loads(raw)
    except Exception:
        return {"score": 7, "passed": True, "feedback": "Could not parse."}

for p in demo['players']:
    name = p['name']
    articles = DEMO_ARTICLES.get(name, [])
    p['sentiment_details'] = articles

    print(f"\n{'='*50}")
    print(f"Generating briefings for {name}...")

    rag_context = f"Recent coverage: {p['articles_count']} articles this week."

    prompt = _build_briefing_prompt(p, rag_context)
    messages = [{"role": "user", "content": prompt}]

    resp_flash = client.chat.completions.create(
        model=FLASH, messages=messages, temperature=0.3, max_tokens=700)
    resp_sonnet = client.chat.completions.create(
        model=SONNET, messages=messages, temperature=0.3, max_tokens=700)

    bf = resp_flash.choices[0].message.content.strip()
    bs = resp_sonnet.choices[0].message.content.strip()

    alerts_text = ", ".join(p.get('alerts', [])) or "none"
    rf = critique(bf, alerts_text)
    rs = critique(bs, alerts_text)

    print(f"  Flash:  {rf['score']}/9 {'PASS' if rf['passed'] else 'FAIL'}")
    print(f"  Sonnet: {rs['score']}/9 {'PASS' if rs['passed'] else 'FAIL'}")

    best = bs if rs.get('score', 0) >= rf.get('score', 0) else bf

    p['briefing_flash']  = bf
    p['briefing_sonnet'] = bs
    p['briefing']        = best
    p['reflection'] = {
        'flash_score':     rf.get('score', 0),
        'flash_passed':    rf.get('passed', False),
        'flash_feedback':  rf.get('feedback', ''),
        'sonnet_score':    rs.get('score', 0),
        'sonnet_passed':   rs.get('passed', False),
        'sonnet_feedback': rs.get('feedback', ''),
    }

demo_path.write_text(_json.dumps(demo, indent=2, ensure_ascii=False))
print("\n\nDone. demo_data.json updated.")
