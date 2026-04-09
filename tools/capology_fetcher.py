"""
Capology salary + contract data via Playwright.

Capology is the best public source for football player wages and contract details.
We use Playwright (already in the stack) instead of ScraperFC's Selenium approach.

Data returned per player:
- weekly_eur      : estimated gross weekly salary in EUR
- annual_eur      : estimated gross annual salary in EUR
- contract_signed : date the current contract was signed
- contract_expires: contract expiry date (ISO format YYYY-MM-DD)
- years_remaining : full seasons left on contract

Limitations:
- Salary figures are estimates (Capology label them as such)
- Saudi Pro League and some minor leagues are not covered
- Data cached locally per (league, season) to avoid repeated scraping

Rate limiting: 2s sleep between page fetches (Capology is less aggressive than TM).
"""

import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
import json

from playwright.sync_api import sync_playwright, Browser, Playwright
from bs4 import BeautifulSoup

# Reuse module-level browser (same pattern as transfermarkt.py)
_pw: Playwright | None = None
_browser: Browser | None = None

# Local cache dir: data/capology_cache/{league}_{season}.json
CACHE_DIR = Path("data/capology_cache")

# League name → Capology URL path
LEAGUE_PATHS: dict[str, str] = {
    "ENG-Premier League": "uk/premier-league",
    "ESP-La Liga":        "es/la-liga",
    "FRA-Ligue 1":        "fr/ligue-1",
    "ITA-Serie A":        "it/serie-a",
    "GER-Bundesliga":     "de/1-bundesliga",
    "POR-Primeira Liga":  "pt/primeira-liga",
    "SAU-Saudi Pro League": "sa/saudi-pro-league",
}

# Map club → league (same as fbref_fetcher)
CLUB_TO_LEAGUE: dict[str, str] = {
    "FC Barcelona": "ESP-La Liga",
    "Real Madrid": "ESP-La Liga",
    "Atletico Madrid": "ESP-La Liga",
    "Manchester City": "ENG-Premier League",
    "Manchester United": "ENG-Premier League",
    "Chelsea": "ENG-Premier League",
    "Arsenal": "ENG-Premier League",
    "Liverpool": "ENG-Premier League",
    "Paris Saint-Germain": "FRA-Ligue 1",
    "PSG": "FRA-Ligue 1",
    "Juventus": "ITA-Serie A",
    "AC Milan": "ITA-Serie A",
    "Inter Milan": "ITA-Serie A",
    "Napoli": "ITA-Serie A",
    "Bayern Munich": "GER-Bundesliga",
    "Borussia Dortmund": "GER-Bundesliga",
    "Al-Nassr": "SAU-Saudi Pro League",
    "Al Nassr": "SAU-Saudi Pro League",
    "Al-Hilal": "SAU-Saudi Pro League",
    "Al-Ittihad": "SAU-Saudi Pro League",
}

CURRENT_SEASON = "2025-2026"


@dataclass
class PlayerContract:
    player: str
    league: str
    weekly_eur: float | None
    annual_eur: float | None
    contract_signed: str | None    # ISO date or None
    contract_expires: str | None   # ISO date or None
    years_remaining: int | None


def _get_browser() -> Browser:
    global _pw, _browser
    if _browser is None or not _browser.is_connected():
        if _pw is None:
            _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(headless=True)
    return _browser


def _normalize(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _parse_eur(text: str) -> float | None:
    text = text.replace("\xa0", "").strip()
    m = re.search(r"[\d,.]+", text)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _parse_date(text: str) -> str | None:
    """Convert 'Jun 30, 2026' or 'Jul 1, 2024' to YYYY-MM-DD."""
    text = text.strip()
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", text)
    if m:
        mon_code = months.get(m.group(1)[:3].lower())
        if mon_code:
            return f"{m.group(3)}-{mon_code}-{int(m.group(2)):02d}"
    return None


def _fetch_league_page(league_path: str) -> list[dict]:
    """Scrape all players from a Capology league page (all pagination)."""
    browser = _get_browser()
    url = f"https://www.capology.com/{league_path}/salaries/"

    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-US",
    )
    page = ctx.new_page()
    time.sleep(2)
    page.goto(url, wait_until="networkidle", timeout=30_000)

    # Click "100 per page" button to minimise pagination
    try:
        page.click("a.page-link:text('100')", timeout=5_000)
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass

    players: list[dict] = []
    visited_pages: set[str] = set()

    while True:
        soup = BeautifulSoup(page.content(), "html.parser")
        table = soup.find("table", id="table")
        if not table:
            break

        for row in table.find_all("tr")[2:]:  # skip two header rows
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 7:
                continue
            player_name = cells[0]
            if not player_name or player_name.isdigit():
                continue
            players.append({
                "name":             player_name,
                "weekly_eur":       _parse_eur(cells[2]) if len(cells) > 2 else None,
                "annual_eur":       _parse_eur(cells[3]) if len(cells) > 3 else None,
                "contract_signed":  _parse_date(cells[5]) if len(cells) > 5 else None,
                "contract_expires": _parse_date(cells[6]) if len(cells) > 6 else None,
                "years_remaining":  int(cells[7]) if len(cells) > 7 and cells[7].isdigit() else None,
            })

        # Check for next page
        active = soup.find("li", class_="page-item active")
        current = active.get_text(strip=True) if active else None
        if current in visited_pages:
            break
        if current:
            visited_pages.add(current)

        next_btn = soup.find("a", class_="page-link", string="Next")
        if not next_btn:
            break
        try:
            page.click("a.page-link:text('Next')", timeout=5_000)
            page.wait_for_load_state("networkidle", timeout=10_000)
            time.sleep(1)
        except Exception:
            break

    ctx.close()
    return players


def _load_cache(league: str, season: str) -> list[dict] | None:
    path = CACHE_DIR / f"{league.replace('/', '_')}_{season}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _save_cache(league: str, season: str, data: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{league.replace('/', '_')}_{season}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_league_salaries(league: str, season: str = CURRENT_SEASON) -> list[dict]:
    """
    Return all player salary records for a league season.
    Results are cached locally; subsequent calls use the cache.
    """
    cached = _load_cache(league, season)
    if cached is not None:
        return cached

    league_path = LEAGUE_PATHS.get(league)
    if not league_path:
        return []

    players = _fetch_league_page(league_path)
    _save_cache(league, season, players)
    return players


def get_player_contract(
    player_name: str,
    club: str,
    season: str = CURRENT_SEASON,
) -> PlayerContract | None:
    """
    Look up salary and contract details for a specific player.

    Uses club name to determine the league, fetches (or loads from cache)
    all player records, then matches by name (accent-insensitive).
    """
    league = CLUB_TO_LEAGUE.get(club)
    if not league:
        return None

    players = get_league_salaries(league, season)
    needle = _normalize(player_name)

    match = None
    for p in players:
        if _normalize(p["name"]) == needle:
            match = p
            break
    if match is None:
        for p in players:
            norm = _normalize(p["name"])
            if needle in norm or norm in needle:
                match = p
                break

    if match is None:
        return None

    return PlayerContract(
        player=match["name"],
        league=league,
        weekly_eur=match.get("weekly_eur"),
        annual_eur=match.get("annual_eur"),
        contract_signed=match.get("contract_signed"),
        contract_expires=match.get("contract_expires"),
        years_remaining=match.get("years_remaining"),
    )


if __name__ == "__main__":
    test = [
        ("Bernardo Silva", "Manchester City"),
        ("Lamine Yamal", "FC Barcelona"),
        ("Vitinha", "Paris Saint-Germain"),
    ]
    for name, club in test:
        print(f"\n{name} ({club})")
        result = get_player_contract(name, club)
        if result:
            print(f"  Weekly: €{result.weekly_eur:,.0f}" if result.weekly_eur else "  Weekly: N/A")
            print(f"  Annual: €{result.annual_eur:,.0f}M" if result.annual_eur else "  Annual: N/A")
            print(f"  Contract: {result.contract_signed} → {result.contract_expires} ({result.years_remaining} yrs left)")
        else:
            print("  Not found (league not supported or player not listed)")
