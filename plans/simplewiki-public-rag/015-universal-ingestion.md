# 015 — Universal Ingestion (`ser add`)

Status: IN PROGRESS. Dependencies: 004, 006, 012, 014.
Outcome: Transform `ser` from a Simple English Wikipedia engine into a universal local RAG engine capable of polymorphic ingestion without flags (`ser add <target>`). Supports Markdown vaults, codebases, plain text, PDFs via `pymupdf4llm`, web URLs, and Wikipedia title fallback with nearest-match suggestions.

---

## 1. Outcome and Ownership

Own `src/ser/ingest/` (router, models, handlers for text, code, PDF, web, audio, vision), `src/ser/chunk.py` (flexible thresholding & metadata), `src/ser/points.py` (source_type payload enrichment), and `src/ser/cli.py` (`ser add` and `/add` REPL commands).

---

## 2. Polymorphic Routing Specification

`ser add <target>` accepts any arbitrary string and resolves it through a zero-flag decision hierarchy:

1. **Web URL** (`http://` or `https://`):
   - Fetches via `httpx` with desktop browser User-Agent.
   - Cleans HTML boilerplate (scripts, styles, nav, footer, ads) into structured prose/markdown.
   - Sets `url` to the web address and `source_type="web"`.

2. **Local Directory** (`Path(target).is_dir()`):
   - Recursively walks file tree (`Path.rglob("*")`).
   - Ignores noise directories: `.git/`, `.venv/`, `node_modules/`, `__pycache__/`, `dist/`, `build/`.
   - Ingests all supported files in parallel/batch with a Rich progress bar.

3. **Local File** (`Path(target).is_file()`):
   - Dispatches by extension:
     - **Markdown** (`.md`, `.markdown`): Preserves `#`, `##`, `###` heading hierarchy into breadcrumbs.
     - **Plain text** (`.txt`, `.log`, `.csv`, `.tsv`): Paragraph sliding-window chunks.
     - **Code** (`.py`, `.rs`, `.ts`, `.js`, `.cpp`, `.c`, `.go`): Function/class block preservation.
     - **PDF** (`.pdf`): Probes text layer; extracts Markdown tables and headings via `pymupdf4llm` in ~125ms/page.
     - **Audio** (`.mp3`, `.wav`, `.m4a`, `.mp4`, `.flac`): Lazy-loads `faster-whisper` (`tiny.en`), producing timestamped chunks.
     - **Images** (`.png`, `.jpg`, `.jpeg`): Windows Native OCR (`winsdk`) for instant text extraction; Ollama Vision for scene descriptions.
   - Sets `url` to clickable `file:///...` URI.

4. **Wikipedia Search & Nearest-Match Fallback**:
   - If target is neither a URL nor an existing path on disk, queries the Wikipedia Action API.
   - If exact match exists: Ingests prose and section headings.
   - If not exact: Queries Wikipedia search API for top 3 closest titles and suggests them or ingests closest match. If completely unknown, returns a clean 404 error.

---

## 3. Storage & Deduplication

- Every ingested document receives a deterministic `page_id` (UUIDv5 of `source_uri`).
- Every chunk receives `chunk_id = f"{page_id}-{chunk_index}"`.
- Point ID in Qdrant is `uuid5(NAMESPACE_DNS, chunk_id)`:
  - Re-ingesting an updated file or directory overwrites existing points in-place idempotently without duplicating vectors or memory.
- Unified payload schema:
  - `chunk_id`: `str`
  - `doc_id`: `str`
  - `title`: `str`
  - `url`: `str` (`file:///...` or `https://...`)
  - `source_type`: `str` (`"markdown"`, `"pdf"`, `"code"`, `"audio"`, `"image"`, `"web"`, `"wiki"`)
  - `chunk_index`: `int`
  - `breadcrumb`: `str`
  - `text`: `str`

---

## 4. Verification Gates

1. `ser add README.md` -> successfully extracts and chunks Markdown with heading breadcrumbs.
2. `ser add <sample>.pdf` -> parses multi-column layout with tables using `pymupdf4llm`.
3. `ser add "Albert Einstein"` -> detects non-path, retrieves Wikipedia article live, and upserts.
4. `ser add "NonExistentTopic12345"` -> returns 404 with helpful suggestions.
5. `ser search "<query>"` -> displays results citing both Wikipedia and local files with clickable file links.
