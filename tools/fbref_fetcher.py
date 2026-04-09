"""
FBref player season stats via soccerdata.

Used as a fallback/supplement to API-Football when:
- A player is not found by ID in API-Football
- Season cache is stale (API-Football caches by player_id + season)
- Richer stats are needed (xG, progressive carries, etc.)

FBref rate limit: ~7 seconds between requests (enforced by soccerdata automatically).
Data is cached locally in ~/soccerdata/data/FBref/ after first fetch.
"""

import unicodedata
from dataclasses import dataclass

import soccerdata as sd

# Map from club name → soccerdata league key used by FBref
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
}

# Season string format for soccerdata: "2025" means 2025/26 season
CURRENT_SEASON = "2025"


@dataclass
class FBrefStats:
    player: str
    league: str
    team: str
    season: str
    appearances: int
    goals: int
    assists: int
    minutes: int
    xg: float | None
    xag: float | None


def _normalize(name: str) -> str:
    """Strip accents and lowercase for fuzzy name matching."""
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def get_player_stats(
    player_name: str,
    club: str,
    season: str = CURRENT_SEASON,
) -> FBrefStats | None:
    """
    Fetch season stats for a player from FBref.

    Determines the correct league from the club name, fetches all players
    in that league, then filters by player name (accent-insensitive).

    Parameters
    ----------
    player_name : str
        Full player name (accents optional).
    club : str
        Club name — used to determine which league to query.
    season : str
        Season start year, e.g. "2025" for 2025/26.

    Returns
    -------
    FBrefStats | None
        Stats for the player, or None if not found.
    """
    league = CLUB_TO_LEAGUE.get(club)
    if not league:
        return None

    try:
        fbref = sd.FBref(leagues=league, seasons=season, no_store=False)
        df = fbref.read_player_season_stats(stat_type="standard")
    except Exception:
        return None

    # DataFrame index: (league, season, team, player)
    # Flatten to search by player name
    df_reset = df.reset_index()

    needle = _normalize(player_name)
    # Try exact match first, then substring
    col = ("Unnamed: player_norm", "player_norm") if ("Unnamed: player_norm", "player_norm") in df_reset.columns else None

    match = None
    for _, row in df_reset.iterrows():
        raw = str(row.get(("Unnamed: 3_level_0", "player"), row.get("player", "")))
        if _normalize(raw) == needle:
            match = row
            break

    if match is None:
        for _, row in df_reset.iterrows():
            raw = str(row.get(("Unnamed: 3_level_0", "player"), row.get("player", "")))
            if needle in _normalize(raw) or _normalize(raw) in needle:
                match = row
                break

    if match is None:
        return None

    def _safe_int(val) -> int:
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return 0

    def _safe_float(val) -> float | None:
        try:
            return round(float(val), 2)
        except (TypeError, ValueError):
            return None

    # Column access — soccerdata uses MultiIndex columns with stat category as level 0
    def _get(row, *keys):
        for k in keys:
            for col in row.index:
                if isinstance(col, tuple) and col[-1] == k:
                    return row[col]
                if col == k:
                    return row[col]
        return None

    return FBrefStats(
        player=player_name,
        league=league,
        team=str(_get(match, "team") or ""),
        season=season,
        appearances=_safe_int(_get(match, "MP")),
        goals=_safe_int(_get(match, "Gls")),
        assists=_safe_int(_get(match, "Ast")),
        minutes=_safe_int(_get(match, "Min")),
        xg=_safe_float(_get(match, "xG")),
        xag=_safe_float(_get(match, "xAG")),
    )


if __name__ == "__main__":
    test_players = [
        ("Bernardo Silva", "Manchester City"),
        ("Lamine Yamal", "FC Barcelona"),
    ]
    for name, club in test_players:
        print(f"\n{name} ({club})")
        stats = get_player_stats(name, club)
        if stats:
            print(f"  {stats.appearances} apps / {stats.goals}g / {stats.assists}a / {stats.minutes} min")
            print(f"  xG: {stats.xg} | xAG: {stats.xag}")
        else:
            print("  Not found")
