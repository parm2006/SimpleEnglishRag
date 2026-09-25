import re
import uuid
from pathlib import Path
from ser.ingest.models import Document

_MD_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

CODE_EXTS = {
    ".py", ".rs", ".ts", ".js", ".jsx", ".tsx",
    ".cpp", ".c", ".h", ".hpp", ".go", ".java",
    ".toml", ".yaml", ".yml", ".json", ".sql", ".sh",
}


def extract_text_file(path: Path) -> Document:
    """Extracts prose from Markdown, plain text, and code files into a Document."""
    resolved = path.resolve()
    url = resolved.as_uri()
    page_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
    ext = resolved.suffix.lower()

    try:
        content = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = resolved.read_text(encoding="latin-1", errors="replace")

    title = resolved.stem.replace("_", " ").replace("-", " ").title()

    if ext in (".md", ".markdown", ".mdx"):
        source_type = "markdown"
        title_match = _MD_TITLE_RE.search(content)
        if title_match:
            title = title_match.group(1).strip()
        doc_text = content
    elif ext == ".py":
        source_type = "code"
        title = resolved.name
        doc_text = content
    elif ext in CODE_EXTS:
        source_type = "code"
        title = resolved.name
        doc_text = f"# File: {resolved.name}\n\n{content}"
    else:
        source_type = "text"
        title = resolved.name
        doc_text = f"# Document: {title}\n\n{content}"

    return Document(
        page_id=page_id,
        title=title,
        url=url,
        text=doc_text,
        source_type=source_type,
    )
