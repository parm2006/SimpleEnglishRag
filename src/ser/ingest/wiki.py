import httpx
from ser.ingest.models import Document

WIKI_API = "https://simple.wikipedia.org/w/api.php"
USER_AGENT = "SimpleEnglishRAG/0.1 (educational project)"


def fetch_wiki_article(title: str) -> Document | None:
    """Fetches full plain text prose for a Wikipedia article by title."""
    headers = {"User-Agent": USER_AGENT}
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": "1",
        "titles": title,
        "format": "json",
        "redirects": "1",
    }

    try:
        response = httpx.get(WIKI_API, params=params, headers=headers, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return None
        for page_id, page_info in pages.items():
            if page_id == "-1":
                return None
            clean_title = page_info.get("title", title)
            return Document(
                page_id=str(page_id),
                title=clean_title,
                url=f"https://simple.wikipedia.org/wiki/{clean_title.replace(' ', '_')}",
                text=page_info.get("extract", "").strip(),
                source_type="wiki",
            )
    except Exception:
        return None
    return None


def search_wiki_titles(query: str, limit: int = 3) -> list[str]:
    """Queries OpenSearch to find the closest matching article titles for typos/partial queries."""
    headers = {"User-Agent": USER_AGENT}
    params = {
        "action": "opensearch",
        "search": query,
        "limit": limit,
        "format": "json",
    }
    try:
        response = httpx.get(WIKI_API, params=params, headers=headers, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        if len(data) >= 2 and isinstance(data[1], list):
            return [t for t in data[1] if t]
    except Exception:
        pass
    return []
