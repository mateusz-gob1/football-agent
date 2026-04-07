import os
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Article:
    title: str
    url: str
    published_at: str
    description: str
    source: str


def fetch_player_news(player_name: str, club: str = None, days_back: int = 7, max_results: int = 10) -> list[Article]:
    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    query = f'"{player_name}"'
    if club:
        query += f" {club}"

    response = requests.get(
        "https://newsapi.org/v2/everything",
        params={
            "q": query,
            "from": from_date,
            "sortBy": "publishedAt",
            "pageSize": max_results,
            "language": "en",
            "apiKey": os.getenv("NEWS_API_KEY"),
        },
    )
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "ok":
        raise RuntimeError(f"NewsAPI error: {data.get('message')}")

    articles = []
    for item in data.get("articles", []):
        articles.append(Article(
            title=item.get("title") or "",
            url=item.get("url") or "",
            published_at=item.get("publishedAt") or "",
            description=item.get("description") or "",
            source=item.get("source", {}).get("name") or "",
        ))

    return articles


if __name__ == "__main__":
    print("--- Famous player, no club needed ---")
    articles = fetch_player_news("Kylian Mbappe")
    print(f"Found {len(articles)} articles\n")

    print("--- Less known player with club ---")
    articles2 = fetch_player_news("Pablo Garcia", club="Osasuna")
    print(f"Found {len(articles2)} articles\n")
    for a in articles2:
        print(f"[{a.published_at[:10]}] {a.source} — {a.title}")
