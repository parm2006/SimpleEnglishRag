import bz2
import html
import json
from pathlib import Path
import re
from typing import Iterator
import xml.etree.ElementTree as ET

from ser.ingest import Document


def clean_wikitext(text: str) -> str:
    """Strips wikitext markup, templates, infoboxes, and references to extract clean prose."""
    if not text:
        return ""

    # 1. Strip HTML/MediaWiki comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # 2. Strip <ref> tags and content
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<ref[^/>]*/>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?[a-zA-Z][^>]*>", "", text)

    # 3. Strip files, images, categories: [[File:...]], [[Category:...]]
    text = re.sub(r"\[\[(?:File|Image|Category):[^\]]+\]\]", "", text, flags=re.IGNORECASE)

    # 4. Strip templates {{...}} (iteratively for nested templates up to 4 levels)
    for _ in range(4):
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)

    # 5. Convert wikilinks [[Target|Anchor]] -> Anchor, [[Target]] -> Target
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)

    # 6. Convert external links [http... Label] -> Label or strip bare URLs
    text = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", text)
    text = re.sub(r"https?://[^\s\]]+", "", text)

    # 7. Convert headings == Heading == -> \n\nHeading\n
    text = re.sub(r"={2,6}\s*(.*?)\s*={2,6}", r"\n\1\n", text)

    # 8. Strip bold and italics: '''bold''' -> bold, ''italic'' -> italic
    text = re.sub(r"'{2,5}", "", text)

    # 9. Unescape HTML entities & clean excessive blank lines
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_checkpoint(checkpoint_path: Path) -> dict:
    if checkpoint_path.exists():
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_page_id": None, "total_processed": 0}


def save_checkpoint(checkpoint_path: Path, last_page_id: str, total_processed: int) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump({"last_page_id": last_page_id, "total_processed": total_processed}, f)


def iter_dump_articles(
    dump_path: str | Path,
    max_articles: int | None = None,
    checkpoint_path: str | Path | None = None,
    min_length: int = 150,
) -> Iterator[Document]:
    """Streams and parses clean articles from a compressed Wikipedia XML dump.

    Operates in O(1) memory at ~700+ pages/sec.
    """
    path = Path(dump_path)
    if not path.exists():
        raise FileNotFoundError(f"Dump file not found: {path}")

    checkpoint_file = Path(checkpoint_path) if checkpoint_path else None
    checkpoint = load_checkpoint(checkpoint_file) if checkpoint_file else {}
    last_id = checkpoint.get("last_page_id")
    resuming = last_id is not None

    articles_emitted = 0
    current_page_id = None

    with bz2.open(path, "rt", encoding="utf-8", errors="replace") as stream:
        in_page = False
        page_lines: list[str] = []

        for line in stream:
            if "<page>" in line:
                in_page = True
                page_lines = [line]
            elif in_page:
                page_lines.append(line)
                if "</page>" in line:
                    in_page = False
                    page_xml = "".join(page_lines)
                    page_lines = []

                    try:
                        root = ET.fromstring(page_xml)
                    except Exception:
                        continue

                    # 1. Namespace check (ns == "0")
                    ns = root.findtext("{*}ns") or root.findtext("ns")
                    if ns != "0":
                        continue

                    # 2. Skip redirect pages
                    if root.find("{*}redirect") is not None or root.find("redirect") is not None:
                        continue

                    # 3. Extract page ID and Title
                    page_id = root.findtext("{*}id") or root.findtext("id") or ""
                    title = root.findtext("{*}title") or root.findtext("title") or ""
                    current_page_id = page_id

                    # Checkpoint resume check
                    if resuming:
                        if page_id == last_id:
                            resuming = False
                        continue

                    # 4. Extract raw text
                    text_elem = root.find(".//{*}text") or root.find(".//text")
                    raw_text = text_elem.text if text_elem is not None and text_elem.text else ""

                    clean_text = clean_wikitext(raw_text)

                    # 5. Filter stubs (< min_length)
                    if len(clean_text) >= min_length:
                        doc_url = f"https://simple.wikipedia.org/wiki/{title.replace(' ', '_')}"
                        doc = Document(page_id=page_id, title=title, url=doc_url, text=clean_text)
                        articles_emitted += 1
                        yield doc

                        if checkpoint_file and articles_emitted % 50 == 0:
                            save_checkpoint(checkpoint_file, page_id, articles_emitted)

                        if max_articles is not None and articles_emitted >= max_articles:
                            break

    if checkpoint_file and current_page_id:
        save_checkpoint(checkpoint_file, current_page_id, articles_emitted)
