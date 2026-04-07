import os
import json
import requests
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = Path("data/stats_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

API_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": os.getenv("API_FOOTBALL_KEY")}

# La Liga = 140, Premier League = 39, Bundesliga = 78, Serie A = 135, Ligue 1 = 61, UCL = 2
MAJOR_LEAGUES = {140, 39, 78, 135, 61, 2}


@dataclass
class PlayerStats:
    player_id: int
    name: str
    season: int
    appearances: int = 0
    goals: int = 0
    assists: int = 0
    minutes: int = 0
    rating: float | None = None
    league: str = ""
    team: str = ""


@dataclass
class PlayerSearchResult:
    player_id: int
    name: str
    team: str


def search_player(name: str, team: str = None) -> PlayerSearchResult | None:
    """Find player ID by name. Optionally filter by team name."""
    # Try major leagues in order until we find a match
    for league_id in [39, 140, 78, 135, 61]:
        r = requests.get(
            f"{API_BASE}/players",
            headers=HEADERS,
            params={"search": name, "league": league_id, "season": "2024"},
        )
        r.raise_for_status()
        results = r.json().get("response", [])
        if not results:
            continue

        for p in results:
            player = p["player"]
            stats = p.get("statistics", [{}])[0]
            player_team = stats.get("team", {}).get("name", "")

            if team and team.lower() not in player_team.lower():
                continue

            return PlayerSearchResult(
                player_id=player["id"],
                name=player["name"],
                team=player_team,
            )

    return None


def get_player_stats(player_id: int, season: int = 2024) -> PlayerStats | None:
    """Fetch season stats for a player. Uses local cache to save API quota."""
    cache_file = CACHE_DIR / f"{player_id}_{season}.json"

    if cache_file.exists():
        with open(cache_file) as f:
            return PlayerStats(**json.load(f))

    r = requests.get(
        f"{API_BASE}/players",
        headers=HEADERS,
        params={"id": player_id, "season": season},
    )
    r.raise_for_status()
    response = r.json().get("response", [])
    if not response:
        return None

    p = response[0]
    player = p["player"]

    # Pick best stats: prefer major league with most appearances
    best = None
    best_apps = -1
    for stat in p.get("statistics", []):
        league_id = stat.get("league", {}).get("id")
        apps = stat.get("games", {}).get("appearences") or 0
        if league_id in MAJOR_LEAGUES and apps > best_apps:
            best = stat
            best_apps = apps
    if not best and p.get("statistics"):
        best = p["statistics"][0]
    if not best:
        return None

    result = PlayerStats(
        player_id=player_id,
        name=player["name"],
        season=season,
        appearances=best["games"].get("appearences") or 0,
        goals=best["goals"].get("total") or 0,
        assists=best["goals"].get("assists") or 0,
        minutes=best["games"].get("minutes") or 0,
        rating=float(best["games"]["rating"]) if best["games"].get("rating") else None,
        league=best["league"].get("name", ""),
        team=best["team"].get("name", ""),
    )

    with open(cache_file, "w") as f:
        json.dump(result.__dict__, f)

    return result


if __name__ == "__main__":
    print("Searching for Mbappe...")
    found = search_player("Mbappe")
    if found:
        print(f"Found: {found.name} (ID: {found.player_id}) at {found.team}\n")
        stats = get_player_stats(found.player_id)
        if stats:
            print(f"Season 2024 — {stats.league} ({stats.team})")
            print(f"  Apps: {stats.appearances} | Goals: {stats.goals} | Assists: {stats.assists} | Minutes: {stats.minutes}")
            print(f"  Rating: {stats.rating}")
