import json
from dataclasses import dataclass
from pathlib import Path
from tools.stats_fetcher import search_player

PLAYERS_FILE = Path("data/players.json")


@dataclass
class Player:
    name: str
    club: str
    position: str
    transfermarkt_url: str
    api_football_id: int | None = None


def load_players() -> list[Player]:
    if not PLAYERS_FILE.exists():
        return []
    with open(PLAYERS_FILE) as f:
        return [Player(**p) for p in json.load(f)]


def save_players(players: list[Player]) -> None:
    with open(PLAYERS_FILE, "w") as f:
        json.dump([p.__dict__ for p in players], f, indent=2)


def add_player(name: str, club: str, position: str, transfermarkt_url: str) -> Player:
    """
    Add a player to the roster.
    transfermarkt_url is required — find it manually on transfermarkt.com to avoid wrong player matches.
    API-Football ID is looked up automatically using name + club.
    """
    players = load_players()

    if any(p.name.lower() == name.lower() for p in players):
        raise ValueError(f"{name} is already in the roster")

    if not transfermarkt_url.startswith("https://www.transfermarkt.com/"):
        raise ValueError("transfermarkt_url must be a valid transfermarkt.com profile URL")

    print(f"Looking up {name} in API-Football...")
    result = search_player(name, team=club)
    api_id = result.player_id if result else None

    if api_id:
        print(f"Found: {result.name} (ID: {api_id}) at {result.team}")
    else:
        print(f"Warning: could not find {name} in API-Football — stats won't be available")

    player = Player(
        name=name,
        club=club,
        position=position,
        transfermarkt_url=transfermarkt_url,
        api_football_id=api_id,
    )
    players.append(player)
    save_players(players)
    return player


def remove_player(name: str) -> bool:
    players = load_players()
    filtered = [p for p in players if p.name.lower() != name.lower()]
    if len(filtered) == len(players):
        return False
    save_players(filtered)
    return True


if __name__ == "__main__":
    print("Current roster:")
    for p in load_players():
        print(f"  {p.name} ({p.club}, {p.position})")
        print(f"    API-Football ID: {p.api_football_id}")
        print(f"    Transfermarkt:   {p.transfermarkt_url}")
