"""
Fix contract dates + remove fake article URLs in demo_data.json.
All dates are consistent with snapshot date: April 9, 2026.
No briefing regeneration needed.
"""
import json
from pathlib import Path
from datetime import date

SNAPSHOT = date(2026, 4, 9)

def days_until(expiry_str):
    exp = date.fromisoformat(expiry_str)
    return (exp - SNAPSHOT).days

# Realistic contracts as of April 2026
CONTRACTS = {
    "Lamine Yamal":        "2031-06-30",  # signed long-term extension at 17
    "Vitinha":             "2028-06-30",  # PSG mid-term deal
    "Joao Neves":          "2030-06-30",  # PSG locked him down long-term
    "Ruben Dias":          "2027-06-30",  # City extension signed 2024
    "Pedro Neto":          "2031-06-30",  # Chelsea gave him 6-year deal on arrival
    "Goncalo Ramos":       "2029-06-30",  # PSG deal
    "Francisco Conceicao": "2029-06-30",  # Porto/Juve loan with purchase option
    "Bernardo Silva":      "2026-06-30",  # expires in ~83 days — real alert
    "Joao Felix":          "2027-06-30",  # Chelsea kept him after loan return
    "Cristiano Ronaldo":   "2027-06-30",  # Al-Nassr renewal signed late 2025
}

demo_path = Path("data/demo_data.json")
demo = json.loads(demo_path.read_text(encoding="utf-8"))

for p in demo["players"]:
    name = p["name"]

    # Fix contract
    if name in CONTRACTS:
        exp = CONTRACTS[name]
        p["contract_expires"] = exp
        p["days_until_expiry"] = days_until(exp)

    # Remove fake article URLs — keep title, sentiment, reason
    for art in p.get("sentiment_details", []):
        art["url"] = ""

    # Rebuild alerts consistently
    alerts = []
    d = p["days_until_expiry"]
    if d < 0:
        alerts.append("Contract already expired")
    elif d < 180:
        alerts.append(f"Contract expiring soon: {p['contract_expires']} ({d} days)")

    sentiment = p.get("sentiment_overall", "neutral")
    if sentiment == "negative":
        alerts.append(f"Negative media sentiment — {p['articles_count']} articles this week")
    if sentiment == "no coverage":
        alerts.append("No media coverage in the last 7 days")

    rating = p.get("rating")
    apps = p.get("appearances", 0)
    if apps > 0 and rating and rating < 7.0:
        alerts.append(f"Below-average rating: {rating:.2f} in {p.get('league','')}")

    p["alerts"] = alerts
    print(f"{name}: contract={p['contract_expires']} ({p['days_until_expiry']}d) | alerts={alerts}")

# Update system snapshot date
demo["system_info"]["last_run"] = "2026-04-09"
total_alerts = sum(len(p["alerts"]) for p in demo["players"])
demo["system_info"]["alerts_count"] = total_alerts

demo_path.write_text(json.dumps(demo, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nDone. Total alerts: {total_alerts}")
