import httpx
from ser.ingest.models import Document

SIMPLE_WIKI_API = "https://simple.wikipedia.org/w/api.php"
MAIN_WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "SimpleEnglishRAG/0.1 (educational project)"


def _fetch_from_api(api_url: str, title: str) -> Document | None:
    """Fetches a Wikipedia article from a given API endpoint. Returns None if not found."""
    is_simple = "simple.wikipedia" in api_url
    wiki_base = "https://simple.wikipedia.org/wiki" if is_simple else "https://en.wikipedia.org/wiki"
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
        response = httpx.get(api_url, params=params, headers=headers, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return None
        for page_id, page_info in pages.items():
            if page_id == "-1":
                return None
            clean_title = page_info.get("title", title)
            text = page_info.get("extract", "").strip()
            if not text:
                return None
            return Document(
                page_id=str(page_id),
                title=clean_title,
                url=f"{wiki_base}/{clean_title.replace(' ', '_')}",
                text=text,
                source_type="wiki",
            )
    except Exception:
        return None
    return None


def fetch_wiki_article(title: str) -> Document | None:
    """Fetches a Wikipedia article by title.

    Tries Simple English Wikipedia first. If the article is not found there,
    falls back to the main English Wikipedia automatically.
    """
    doc = _fetch_from_api(SIMPLE_WIKI_API, title)
    if doc:
        return doc
    # Simple Wikipedia didn't have it — try main English Wikipedia
    return _fetch_from_api(MAIN_WIKI_API, title)


def _search_titles_from_api(api_url: str, query: str, limit: int) -> list[str]:
    """OpenSearch against a single Wikipedia API endpoint."""
    headers = {"User-Agent": USER_AGENT}
    params = {
        "action": "opensearch",
        "search": query,
        "limit": limit,
        "format": "json",
    }
    try:
        response = httpx.get(api_url, params=params, headers=headers, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        if len(data) >= 2 and isinstance(data[1], list):
            return [t for t in data[1] if t]
    except Exception:
        pass
    return []


def search_wiki_titles(query: str, limit: int = 3) -> list[str]:
    """Finds closest matching article titles via OpenSearch.

    Searches Simple Wikipedia first; if no results, falls back to main Wikipedia.
    Deduplicates while preserving order.
    """
    simple_results = _search_titles_from_api(SIMPLE_WIKI_API, query, limit)
    if simple_results:
        return simple_results
    return _search_titles_from_api(MAIN_WIKI_API, query, limit)
