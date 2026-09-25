import re
import uuid
import httpx
from ser.ingest.models import Document

_TAG_STRIP_RE = re.compile(r"<(script|style|nav|footer|header|aside|noscript|svg|form)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
_H3_RE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.IGNORECASE | re.DOTALL)
_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def extract_web_url(url: str) -> Document:
    """Fetches a webpage, strips navigational boilerplate, and returns a clean Markdown Document."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=15.0)
    response.raise_for_status()
    raw_html = response.text

    # Extract title
    title_match = _TITLE_RE.search(raw_html)
    title = title_match.group(1).strip() if title_match else url

    # Remove heavy non-content sections
    cleaned = _TAG_STRIP_RE.sub("", raw_html)

    # Convert common content tags to Markdown equivalents
    cleaned = _H1_RE.sub(r"\n# \1\n", cleaned)
    cleaned = _H2_RE.sub(r"\n## \1\n", cleaned)
    cleaned = _H3_RE.sub(r"\n### \1\n", cleaned)
    cleaned = _P_RE.sub(r"\n\1\n", cleaned)
    cleaned = _BR_RE.sub("\n", cleaned)

    # Strip remaining HTML tags
    plain_text = _HTML_TAG_RE.sub(" ", cleaned)

    # Clean up excess whitespace and decode HTML entities
    import html
    decoded = html.unescape(plain_text)
    lines = [l.strip() for l in decoded.splitlines()]
    prose = "\n".join(l for l in lines if l)

    # Ensure document starts with a title header
    final_text = f"# {title}\n\n{prose}"
    page_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))

    return Document(
        page_id=page_id,
        title=title,
        url=url,
        text=final_text,
        source_type="web",
    )
