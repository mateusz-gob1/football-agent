from pathlib import Path
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from tools.news_fetcher import Article

CHROMA_DIR = str(Path("data/chroma_db"))
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_embeddings = None
_store = None


def _get_store() -> Chroma:
    global _embeddings, _store
    if _store is None:
        _embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
        _store = Chroma(
            collection_name="football_articles",
            embedding_function=_embeddings,
            persist_directory=CHROMA_DIR,
        )
    return _store


def store_articles(player_name: str, articles: list[Article]) -> int:
    """Embed and store articles for a player. Skips duplicates by URL."""
    if not articles:
        return 0

    store = _get_store()

    existing = store.get(where={"player": player_name})
    existing_urls = set(m.get("url", "") for m in existing["metadatas"])

    docs = []
    for a in articles:
        if a.url in existing_urls:
            continue
        content = f"{a.title}. {a.description}"
        docs.append(Document(
            page_content=content,
            metadata={
                "player": player_name,
                "title": a.title,
                "url": a.url,
                "source": a.source,
                "published_at": a.published_at,
            },
        ))

    if docs:
        store.add_documents(docs)

    return len(docs)


def retrieve_context(player_name: str, k: int = 5) -> str:
    """Retrieve k most relevant articles for a player as a formatted string."""
    store = _get_store()

    results = store.similarity_search(
        query=player_name,
        k=k,
        filter={"player": player_name},
    )

    if not results:
        return "No stored articles found."

    lines = []
    for doc in results:
        date = doc.metadata.get("published_at", "")[:10]
        source = doc.metadata.get("source", "")
        lines.append(f"[{date}] {source}: {doc.page_content}")

    return "\n".join(lines)


if __name__ == "__main__":
    from tools.news_fetcher import fetch_player_news

    articles = fetch_player_news("Kylian Mbappe", club="Real Madrid")
    added = store_articles("Kylian Mbappe", articles)
    print(f"Stored {added} new articles\n")

    context = retrieve_context("Kylian Mbappe")
    print("Retrieved context:")
    print(context)
