import re
from dataclasses import dataclass

from ser.ingest import Document, fetch_wiki_article

_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_WIKI_HEADING_RE = re.compile(r"^(={1,6})\s*(.*?)\s*\1$")


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    url: str
    chunk_index: int
    text: str
    breadcrumb: str = ""
    source_type: str = "wiki"

    def get_embed_text(self) -> str:
        """Returns formatted text injected with the heading breadcrumb for dense embedding.
        
        Injecting the hierarchical breadcrumb grounds isolated paragraphs in the overarching
        document topic and specific section context, substantially improving semantic retrieval.
        """
        if self.breadcrumb:
            return f"{self.breadcrumb}\n\n{self.text}"
        if self.title and self.title != "NOT FOUND":
            return f"{self.title}\n\n{self.text}"
        return self.text


def parse_heading(line: str) -> tuple[int, str] | None:
    """Detects Markdown (# Heading) or MediaWiki (== Heading ==) heading lines.
    
    Returns a tuple of (heading_level, clean_heading_text) or None if not a heading.
    """
    cleaned = line.strip()
    if not cleaned:
        return None

    # Check Markdown: # Title (1-6)
    md_match = _MD_HEADING_RE.match(cleaned)
    if md_match:
        level = len(md_match.group(1))
        heading_text = md_match.group(2).strip()
        return level, heading_text

    # Check MediaWiki: == Section == (1-6)
    wiki_match = _WIKI_HEADING_RE.match(cleaned)
    if wiki_match:
        level = len(wiki_match.group(1))
        heading_text = wiki_match.group(2).strip()
        return level, heading_text

    return None


def _split_section_text(
    text: str,
    doc_id: str,
    title: str,
    url: str,
    breadcrumb: str,
    start_index: int,
    chunk_size: int = 1200,
    overlap: int = 200,
    source_type: str = "wiki",
) -> tuple[list[Chunk], int]:
    """Splits a section's text into word-boundary chunks inheriting the section breadcrumb."""
    chunks: list[Chunk] = []
    clean_text = text.strip()
    if not clean_text:
        return chunks, start_index

    # If the entire section fits comfortably in one chunk, keep it intact
    if len(clean_text) <= chunk_size:
        chk = Chunk(
            chunk_id=f"{doc_id}-{start_index}",
            doc_id=doc_id,
            title=title,
            url=url,
            chunk_index=start_index,
            text=clean_text,
            breadcrumb=breadcrumb,
            source_type=source_type,
        )
        return [chk], start_index + 1

    # Otherwise, slide across word boundaries with specified overlap
    start = 0
    curr_index = start_index
    while start < len(clean_text):
        end = start + chunk_size
        if end < len(clean_text):
            space_pos = clean_text.rfind(" ", start + (chunk_size // 2), end)
            if space_pos != -1:
                end = space_pos

        chunk_text = clean_text[start:end].strip()
        if chunk_text:
            chk = Chunk(
                chunk_id=f"{doc_id}-{curr_index}",
                doc_id=doc_id,
                title=title,
                url=url,
                chunk_index=curr_index,
                text=chunk_text,
                breadcrumb=breadcrumb,
                source_type=source_type,
            )
            chunks.append(chk)
            curr_index += 1

        start = end - overlap
        if start >= len(clean_text) - overlap:
            break

    return chunks, curr_index


def create_chunks(
    doc: Document, chunk_size: int = 1200, overlap: int = 200
) -> list[Chunk]:
    """Splits a document into hierarchy-aware chunks with heading breadcrumbs.
    
    Tracks section hierarchy across Markdown and MediaWiki documents, injecting
    breadcrumb trails (e.g. 'Apollo 11 > Mission background > Spacecraft')
    into every generated chunk.
    """
    text = doc.text.strip()
    if len(text) < 20 or text == "NOT FOUND":
        return []

    doc_id = doc.page_id
    url = doc.url
    title = doc.title
    source_type = getattr(doc, "source_type", "wiki")

    lines = text.splitlines()

    # Track active hierarchy: level -> heading text
    # Level 0 is reserved for the document root title
    current_headings: dict[int, str] = {}
    if title and title != "NOT FOUND":
        current_headings[0] = title

    def build_breadcrumb() -> str:
        if not current_headings:
            return title or ""
        return " > ".join(current_headings[k] for k in sorted(current_headings.keys()))

    sections: list[tuple[str, str]] = []  # list of (breadcrumb, section_text)
    current_lines: list[str] = []
    current_breadcrumb = build_breadcrumb()

    for line in lines:
        heading_info = parse_heading(line)
        if heading_info is not None:
            level, h_text = heading_info

            # Flush previous section text if present
            accumulated = "\n".join(current_lines).strip()
            if accumulated:
                sections.append((current_breadcrumb, accumulated))
                current_lines = []

            # If the heading text is identical to doc title, don't duplicate it
            if title and h_text.strip().lower() == title.strip().lower():
                current_headings[0] = h_text
                current_breadcrumb = build_breadcrumb()
                continue

            # Clear any headings at or below this level
            to_remove = [k for k in current_headings if k >= level]
            for k in to_remove:
                del current_headings[k]

            current_headings[level] = h_text
            current_breadcrumb = build_breadcrumb()
        else:
            current_lines.append(line)

    # Flush final section
    final_accumulated = "\n".join(current_lines).strip()
    if final_accumulated:
        sections.append((current_breadcrumb, final_accumulated))

    if not sections:
        return []

    # Chunk sections and assign sequential chunk indices
    all_chunks: list[Chunk] = []
    curr_idx = 0
    for bcrumb, sec_text in sections:
        sec_chunks, curr_idx = _split_section_text(
            text=sec_text,
            doc_id=doc_id,
            title=title,
            url=url,
            breadcrumb=bcrumb,
            start_index=curr_idx,
            chunk_size=chunk_size,
            overlap=overlap,
            source_type=source_type,
        )
        all_chunks.extend(sec_chunks)

    return all_chunks


def main() -> None:
    doc = fetch_wiki_article("Math")
    if not doc:
        print("could not fetch document")
        return
    chunks = create_chunks(doc)
    if not chunks:
        print("could not create chunks")
        return
    print(f"Generated {len(chunks)} chunks for '{doc.title}':")
    for c in chunks[:3]:
        print(f"  [{c.chunk_id}] Breadcrumb: {c.breadcrumb}")
        print(f"  Text preview: {c.text[:80]}...\n")


if __name__ == "__main__":
    main()
