from dotenv import load_dotenv
import os

load_dotenv()

def test_newsapi():
    import requests
    url = "https://newsapi.org/v2/everything"
    params = {"q": "Kylian Mbappe", "pageSize": 1, "apiKey": os.getenv("NEWS_API_KEY")}
    r = requests.get(url, params=params)
    data = r.json()
    if data.get("status") == "ok":
        print(f"[OK] NewsAPI — {data['totalResults']} articles found for 'Mbappe'")
    else:
        print(f"[FAIL] NewsAPI — {data}")

def test_openrouter():
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_BASE_URL"),
    )
    response = client.chat.completions.create(
        model="google/gemini-2.5-flash-lite-preview-09-2025",
        messages=[{"role": "user", "content": "Say 'connection ok' and nothing else."}],
        max_tokens=10,
    )
    print(f"[OK] OpenRouter — model replied: {response.choices[0].message.content.strip()}")

def test_langfuse():
    from langfuse import Langfuse
    lf = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST"),
    )
    lf.auth_check()
    print("[OK] LangFuse — authenticated successfully")

if __name__ == "__main__":
    print("Testing connections...\n")
    for name, fn in [("NewsAPI", test_newsapi), ("OpenRouter", test_openrouter), ("LangFuse", test_langfuse)]:
        try:
            fn()
        except Exception as e:
            print(f"[FAIL] {name} — {e}")
