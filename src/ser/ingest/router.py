from pathlib import Path
from typing import Any
from ser.ingest.models import Document
from ser.ingest.wiki import fetch_wiki_article, search_wiki_titles

IGNORE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".ser", "dist", "build", ".idea", ".vscode",
    ".mypy_cache", ".ruff_cache",
}

EXT_MAP = {
    ".md": "text", ".markdown": "text", ".mdx": "text",
    ".txt": "text", ".log": "text", ".csv": "text", ".tsv": "text",
    ".py": "code", ".rs": "code", ".ts": "code", ".js": "code",
    ".jsx": "code", ".tsx": "code", ".cpp": "code", ".c": "code",
    ".h": "code", ".hpp": "code", ".go": "code", ".java": "code",
    ".toml": "code", ".yaml": "code", ".yml": "code", ".json": "code",
    ".sql": "code", ".sh": "code",
    ".pdf": "pdf",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image", ".bmp": "image",
    ".mp3": "audio", ".wav": "audio", ".m4a": "audio", ".mp4": "audio", ".flac": "audio", ".ogg": "audio",
}


def get_file_kind(path: Path) -> str | None:
    return EXT_MAP.get(path.suffix.lower())


def walk_directory(dir_path: Path) -> list[Path]:
    """Recursively finds all supported files, skipping build/virtualenv noise."""
    matched_files: list[Path] = []
    for p in dir_path.rglob("*"):
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        if p.is_file() and get_file_kind(p) is not None:
            matched_files.append(p)
    return sorted(matched_files)


def process_file(path: Path) -> Document:
    """Dispatches file extraction with zero-cost lazy imports."""
    kind = get_file_kind(path)
    if not kind:
        raise ValueError(f"Unsupported file format: {path.suffix}")

    match kind:
        case "text" | "code":
            from ser.ingest.handlers.text import extract_text_file
            return extract_text_file(path)
        case "pdf":
            from ser.ingest.handlers.pdf import extract_pdf_file
            return extract_pdf_file(path)
        case "image":
            from ser.ingest.handlers.vision import extract_image_file
            return extract_image_file(path)
        case "audio":
            from ser.ingest.handlers.audio import extract_audio_file
            return extract_audio_file(path)
        case _:
            raise ValueError(f"No handler configured for kind: {kind}")


def resolve_target(target: str) -> tuple[str, Any]:
    """Polymorphically resolves an arbitrary user target without flags.
    
    Returns:
      ("url", [Document])
      ("file", [Document])
      ("directory", [Document])
      ("wiki", [Document])
      ("wiki_suggestions", [str])
      ("wiki_404", None)
    """
    clean_target = target.strip().strip("'\"")

    # 1. URL Detection
    if clean_target.startswith(("http://", "https://")):
        from ser.ingest.handlers.web import extract_web_url
        doc = extract_web_url(clean_target)
        return "url", [doc]

    # 2. Local Path Detection
    local_path = Path(clean_target)
    if local_path.exists():
        if local_path.is_dir():
            files = walk_directory(local_path)
            if not files:
                return "empty_directory", []
            docs = [process_file(f) for f in files]
            return "directory", docs
        elif local_path.is_file():
            doc = process_file(local_path)
            return "file", [doc]

    # 3. Wikipedia Fallback (Not a URL, doesn't exist on disk)
    wiki_doc = fetch_wiki_article(clean_target)
    if wiki_doc and wiki_doc.text:
        return "wiki", [wiki_doc]

    # 4. Nearest-match Wikipedia suggestions
    suggestions = search_wiki_titles(clean_target, limit=3)
    if suggestions:
        return "wiki_suggestions", suggestions

    return "wiki_404", None
