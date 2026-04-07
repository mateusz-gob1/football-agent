import os
import json
from dataclasses import dataclass
from langfuse.openai import OpenAI
from langfuse import observe
from dotenv import load_dotenv
from tools.news_fetcher import Article

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL"),
)

MODEL = os.getenv("DEFAULT_MODEL", "google/gemini-2.5-flash-lite-preview-09-2025")


@dataclass
class ArticleSentiment:
    title: str
    sentiment: str  # positive | negative | neutral
    reason: str


@dataclass
class PlayerSentiment:
    player_name: str
    overall: str  # positive | negative | neutral | mixed
    articles: list[ArticleSentiment]
    no_coverage: bool = False


@observe(name="sentiment_analysis")
def analyze_sentiment(player_name: str, articles: list[Article]) -> PlayerSentiment:
    if not articles:
        return PlayerSentiment(
            player_name=player_name,
            overall="no coverage",
            articles=[],
            no_coverage=True,
        )

    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"{i}. Title: {a.title}\n   Description: {a.description}\n\n"

    prompt = f"""Analyze the media sentiment for football player {player_name} based on these articles.

{articles_text}
Return a JSON object with this exact structure:
{{
  "overall": "positive" | "negative" | "neutral" | "mixed",
  "articles": [
    {{
      "title": "article title",
      "sentiment": "positive" | "negative" | "neutral",
      "reason": "one sentence explaining why"
    }}
  ]
}}

Rules:
- overall is "mixed" when there are both positive and negative articles
- reason must be specific to the article content, max 15 words
- respond with JSON only, no extra text"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = json.loads(response.choices[0].message.content)

    article_sentiments = [
        ArticleSentiment(
            title=item["title"],
            sentiment=item["sentiment"],
            reason=item["reason"],
        )
        for item in raw.get("articles", [])
    ]

    return PlayerSentiment(
        player_name=player_name,
        overall=raw.get("overall", "neutral"),
        articles=article_sentiments,
    )


if __name__ == "__main__":
    from tools.news_fetcher import fetch_player_news

    articles = fetch_player_news("Kylian Mbappe")
    print(f"Fetched {len(articles)} articles, analyzing sentiment...\n")

    result = analyze_sentiment("Kylian Mbappe", articles)

    print(f"Player: {result.player_name}")
    print(f"Overall sentiment: {result.overall.upper()}\n")
    for a in result.articles:
        print(f"  [{a.sentiment}] {a.title}")
        print(f"           -> {a.reason}")
