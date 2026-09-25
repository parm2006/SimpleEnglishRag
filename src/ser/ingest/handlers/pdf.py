import uuid
from pathlib import Path
import pymupdf
import pymupdf4llm
from ser.ingest.models import Document


def has_text_layer(path: Path, sample_pages: int = 3) -> bool:
    """Probes the first sample_pages to verify if the PDF contains a real digital text layer."""
    try:
        doc = pymupdf.open(str(path))
        text_count = 0
        for i in range(min(sample_pages, len(doc))):
            text_count += len(doc[i].get_text().strip())
        doc.close()
        return text_count > 50
    except Exception:
        return False


def extract_pdf_file(path: Path) -> Document:
    """Extracts layout-aware Markdown and tables from PDF documents."""
    resolved = path.resolve()
    url = resolved.as_uri()
    page_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))

    # Read metadata title if present
    title = resolved.stem.replace("_", " ").replace("-", " ").title()
    try:
        doc = pymupdf.open(str(resolved))
        meta_title = doc.metadata.get("title")
        if meta_title and len(meta_title.strip()) > 3:
            title = meta_title.strip()
        doc.close()
    except Exception:
        pass

    if not has_text_layer(resolved):
        # Scanned PDF path: fallback to vision OCR
        from ser.ingest.handlers.vision import ocr_scanned_pdf
        markdown_text = ocr_scanned_pdf(resolved)
    else:
        # Digital PDF fast path: layout-aware Markdown extraction
        markdown_text = pymupdf4llm.to_markdown(str(resolved))

    # Ensure document starts with a top-level Markdown title for breadcrumb anchoring
    if not markdown_text.lstrip().startswith("#"):
        markdown_text = f"# {title}\n\n{markdown_text}"

    return Document(
        page_id=page_id,
        title=title,
        url=url,
        text=markdown_text,
        source_type="pdf",
    )
