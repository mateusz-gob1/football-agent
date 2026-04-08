import json
import re
import time
import cloudscraper
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from datetime import date

# cloudscraper handles Cloudflare JS-challenge that plain requests can't pass
_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)


@dataclass
class PlayerMarketData:
    name: str
    market_value_eur: float | None       # millions, e.g. 200.0
    contract_expires: str | None         # "YYYY-MM-DD"
    days_until_expiry: int | None


@dataclass
class ValueHistoryEntry:
    date: str          # "YYYY-MM-DD"
    value_eur: float   # millions
    club: str


@dataclass
class CompetitionStats:
    competition: str
    appearances: int
    goals: int
    assists: int
    minutes: int


@dataclass
class PlayerSeasonData:
    name: str
    season: str                                     # e.g. "25/26"
    competitions: list[CompetitionStats] = field(default_factory=list)
    total_appearances: int = 0
    total_goals: int = 0
    total_assists: int = 0


# ── helpers ────────────────────────────────────────────────────────────────

def _parse_market_value(text: str) -> float | None:
    """Parse '€200.00m' or '€50.00k' into float (millions)."""
    text = text.replace("\xa0", "").strip()
    match = re.search(r"([\d.,]+)\s*([mk]?)", text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    unit = match.group(2).lower()
    if unit == "k":
        value = value / 1000
    return round(value, 2)


def _parse_contract_date(text: str) -> str | None:
    """Extract contract expiry — last DD/MM/YYYY in text."""
    matches = re.findall(r"(\d{2}/\d{2}/\d{4})", text)
    if not matches:
        return None
    day, month, year = matches[-1].split("/")
    return f"{year}-{month}-{day}"


def _url_variant(profile_url: str, section: str) -> str:
    """
    Convert a /profil/ URL to another section.
    e.g. profile_url = '.../joao-felix/profil/spieler/338250'
         section     = 'marktwertverlauf'
    → '.../joao-felix/marktwertverlauf/spieler/338250'
    """
    return re.sub(r"/profil/", f"/{section}/", profile_url)


def _fetch(url: str) -> BeautifulSoup:
    time.sleep(2)
    r = _scraper.get(url, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


# ── public functions ────────────────────────────────────────────────────────

def get_player_market_data(transfermarkt_url: str, player_name: str) -> PlayerMarketData:
    soup = _fetch(transfermarkt_url)

    mv_tag = soup.find("a", class_="data-header__market-value-wrapper")
    market_value = _parse_market_value(mv_tag.get_text()) if mv_tag else None

    contract_expires = None
    for span in soup.find_all("span", class_="data-header__label"):
        if "contract expires" in span.get_text().lower():
            contract_expires = _parse_contract_date(span.parent.get_text())
            break

    days_until_expiry = None
    if contract_expires:
        expiry = date.fromisoformat(contract_expires)
        days_until_expiry = (expiry - date.today()).days

    return PlayerMarketData(
        name=player_name,
        market_value_eur=market_value,
        contract_expires=contract_expires,
        days_until_expiry=days_until_expiry,
    )


def get_market_value_history(transfermarkt_url: str, player_name: str) -> list[ValueHistoryEntry]:
    """
    Scrape the full market value history from Transfermarkt's marktwertverlauf page.

    Transfermarkt embeds chart data as a JSON array inside a <script> block.
    Each entry looks like:
        {"datum_mw":"Dec 18, 2025","x":1765929600000,"y":25000000,"mw":"€25.00m","verein":"Al-Nassr FC","age":"26"}

    Falls back to parsing the HTML table if the JSON pattern is not found.
    """
    url = _url_variant(transfermarkt_url, "marktwertverlauf")
    soup = _fetch(url)

    # Strategy 1: extract Highcharts JSON from <script> tags
    entries = _parse_value_history_from_script(soup)
    if entries:
        return entries

    # Strategy 2: parse HTML table (older page layout)
    return _parse_value_history_from_table(soup, player_name)


def _parse_value_history_from_script(soup: BeautifulSoup) -> list[ValueHistoryEntry]:
    """Extract market value history from embedded Highcharts JSON."""
    for script in soup.find_all("script"):
        text = script.string or ""
        # Look for the data array pattern
        match = re.search(r'"data"\s*:\s*(\[.*?\])', text, re.DOTALL)
        if not match:
            continue
        try:
            raw = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

        entries = []
        for item in raw:
            if not isinstance(item, dict) or "mw" not in item:
                continue
            value = _parse_market_value(item.get("mw", ""))
            if value is None:
                continue
            # datum_mw is like "Dec 18, 2025" or "18. Dez 2025"
            date_str = _parse_tm_date(item.get("datum_mw", ""))
            club = item.get("verein", "")
            if date_str:
                entries.append(ValueHistoryEntry(date=date_str, value_eur=value, club=club))

        if entries:
            return sorted(entries, key=lambda e: e.date)

    return []


def _parse_value_history_from_table(soup: BeautifulSoup, player_name: str) -> list[ValueHistoryEntry]:
    """Fallback: parse <table class='items'> on the marktwertverlauf page."""
    table = soup.find("table", class_="items")
    if not table:
        return []

    entries = []
    for row in table.find_all("tr")[1:]:  # skip header
        cols = row.find_all("td")
        if len(cols) < 4:
            continue
        date_str = _parse_tm_date(cols[0].get_text(strip=True))
        club = cols[2].get_text(strip=True)
        value = _parse_market_value(cols[3].get_text(strip=True))
        if date_str and value is not None:
            entries.append(ValueHistoryEntry(date=date_str, value_eur=value, club=club))

    return sorted(entries, key=lambda e: e.date)


def _parse_tm_date(text: str) -> str | None:
    """
    Parse Transfermarkt date strings to ISO format.
    Handles: "Dec 18, 2025", "Jun 15, 2024", "18. Dec 2025"
    """
    text = text.strip()
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
        # German
        "mär": "03", "mai": "05", "okt": "10", "dez": "12",
        "jan": "01", "feb": "02", "jun": "06", "jul": "07",
        "aug": "08", "sep": "09", "nov": "11",
    }
    # "Dec 18, 2025"
    m = re.match(r"([A-Za-zä]+)\.?\s+(\d{1,2}),?\s+(\d{4})", text)
    if m:
        mon, day, year = m.groups()
        code = months.get(mon[:3].lower())
        if code:
            return f"{year}-{code}-{int(day):02d}"

    # "18. Dez 2025" or "18 Dec 2025"
    m = re.match(r"(\d{1,2})\.?\s+([A-Za-zä]+)\.?\s+(\d{4})", text)
    if m:
        day, mon, year = m.groups()
        code = months.get(mon[:3].lower())
        if code:
            return f"{year}-{code}-{int(day):02d}"

    return None


def get_season_stats(transfermarkt_url: str, player_name: str) -> PlayerSeasonData:
    """
    Scrape current-season stats per competition from the leistungsdaten page.

    The page has a table with competition name, appearances, goals, assists, minutes.
    We return totals + per-competition breakdown.
    """
    url = _url_variant(transfermarkt_url, "leistungsdaten")
    soup = _fetch(url)

    # Detect season label (e.g. "25/26") from dropdown or page heading
    season = _detect_season(soup)

    competitions = []
    table = soup.find("table", class_="items")
    if not table:
        return PlayerSeasonData(name=player_name, season=season)

    for row in table.find_all("tr"):
        # Skip header and total rows
        classes = row.get("class", [])
        if "tfoot" in classes or row.find("th"):
            continue
        cols = row.find_all("td")
        if len(cols) < 6:
            continue

        comp_name = cols[0].get_text(strip=True) or cols[1].get_text(strip=True)
        apps      = _safe_int(cols[2].get_text(strip=True))
        goals     = _safe_int(cols[3].get_text(strip=True))
        assists   = _safe_int(cols[4].get_text(strip=True))
        minutes_text = cols[-1].get_text(strip=True).replace("'", "").replace(".", "")
        minutes   = _safe_int(minutes_text)

        if comp_name and apps > 0:
            competitions.append(CompetitionStats(
                competition=comp_name,
                appearances=apps,
                goals=goals,
                assists=assists,
                minutes=minutes,
            ))

    # Also grab the total row (tfoot)
    tfoot = table.find("tfoot")
    total_apps = total_goals = total_assists = 0
    if tfoot:
        cols = tfoot.find_all("td")
        if len(cols) >= 5:
            total_apps    = _safe_int(cols[2].get_text(strip=True))
            total_goals   = _safe_int(cols[3].get_text(strip=True))
            total_assists = _safe_int(cols[4].get_text(strip=True))
    else:
        total_apps    = sum(c.appearances for c in competitions)
        total_goals   = sum(c.goals for c in competitions)
        total_assists = sum(c.assists for c in competitions)

    return PlayerSeasonData(
        name=player_name,
        season=season,
        competitions=competitions,
        total_appearances=total_apps,
        total_goals=total_goals,
        total_assists=total_assists,
    )


def _detect_season(soup: BeautifulSoup) -> str:
    """Try to read current season label from page (e.g. '25/26')."""
    select = soup.find("select", {"name": re.compile(r"saison", re.I)})
    if select:
        opt = select.find("option", selected=True)
        if opt:
            return opt.get_text(strip=True)
    return "current"


def _safe_int(text: str) -> int:
    try:
        return int(re.sub(r"[^\d]", "", text) or "0")
    except ValueError:
        return 0


# ── CLI test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_players = [
        ("Joao Felix",   "https://www.transfermarkt.com/joao-felix/profil/spieler/338250"),
        ("Bernardo Silva", "https://www.transfermarkt.com/bernardo-silva/profil/spieler/259885"),
    ]

    for name, url in test_players:
        print(f"\n{'='*50}")
        print(f"  {name}")
        print(f"{'='*50}")

        data = get_player_market_data(url, name)
        print(f"  Current value : €{data.market_value_eur}M")
        print(f"  Contract      : {data.contract_expires} ({data.days_until_expiry}d)")

        history = get_market_value_history(url, name)
        print(f"  Value history : {len(history)} entries")
        for entry in history[-4:]:
            print(f"    {entry.date}  €{entry.value_eur}M  ({entry.club})")

        stats = get_season_stats(url, name)
        print(f"  Season {stats.season}: {stats.total_appearances} apps / "
              f"{stats.total_goals}g / {stats.total_assists}a")
        for comp in stats.competitions:
            print(f"    {comp.competition}: {comp.appearances} apps, "
                  f"{comp.goals}g, {comp.assists}a")
