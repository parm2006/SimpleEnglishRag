# 015 — Universal Ingestion (`ser add`)

Status: COMPLETE. Dependencies: 004, 006, 012, 014.
Outcome: Transformed `ser` from a Simple English Wikipedia engine into a universal local RAG engine capable of polymorphic ingestion without flags (`ser add <target>`). Supports Markdown vaults, codebases, plain text, CSV/TSV tables, digital and scanned PDFs, local audio, multimodal images, web URLs, and Wikipedia title fallback with nearest-match suggestions.

---

## 1. Outcome and Ownership

Implemented in `src/ser/ingest/` (router, models, handlers for text, code, PDF, tabular, web, audio, vision), `src/ser/chunk.py` (hierarchy-aware heading chunking), `src/ser/points.py` (source_type payload enrichment), and `src/ser/cli.py` (`ser add` and `/add` REPL commands).

---

## 2. Polymorphic Routing Specification

`ser add <target>` accepts any arbitrary string and resolves it through a zero-flag decision hierarchy:

1. **Web URL** (`http://` or `https://`):
   - Fetches via `httpx` with desktop browser User-Agent.
   - Cleans HTML boilerplate (scripts, styles, nav, footer, ads) into structured prose/markdown.
   - Sets `url` to the web address and `source_type="web"`.

2. **Local Directory** (`Path(target).is_dir()`):
   - Recursively walks file tree (`walk_directory`).
   - Ignores noise directories: `.git/`, `.venv/`, `node_modules/`, `__pycache__/`, `dist/`, `build/`.
   - Ingests all supported files in batch with automatic deduplication.

3. **Local File** (`Path(target).is_file()`):
   - Dispatches by extension:
     - **Markdown** (`.md`, `.markdown`, `.mdx`): Preserves `#`, `##`, `###` heading hierarchy into breadcrumbs.
     - **Plain text** (`.txt`, `.log`): Heading and paragraph sliding-window chunks.
     - **Tabular Data** (`.csv`, `.tsv`): Formats Markdown tables in 30-row batches with repeated column headers.
     - **Code** (`.py`, `.rs`, `.ts`, `.js`, `.cpp`, `.c`, `.go`): Python uses AST function/class extraction; non-Python prepends `# File: {name}` and chunks as text.
     - **Digital PDF** (`.pdf` with text layer): Extracts layout-aware Markdown tables and headings via `pymupdf4llm`.
     - **Scanned PDF** (`.pdf` without text layer): Probes text layer with `has_text_layer()`, rasterizes pages to 150 DPI pixmaps, and extracts text via Windows OCR / Ollama vision.
     - **Audio** (`.mp3`, `.wav`, `.m4a`, `.mp4`, `.flac`): Lazy-loads `faster-whisper` (`tiny.en`), producing timestamped chunks (`[00:00 – 00:05]`).
     - **Images** (`.png`, `.jpg`, `.jpeg`, `.webp`): Checks for local Ollama vision model (`moondream`, `llama3.2-vision`) for deep diagram understanding, falling back to hardware-accelerated Windows Media OCR (`winsdk`) if missing.
   - Sets `url` to clickable `file:///...` URI.

4. **Wikipedia Search & Nearest-Match Fallback**:
   - If target is neither a URL nor an existing path on disk, queries the Wikipedia Action API.
   - If exact match exists: Ingests prose and section headings.
   - If not exact: Queries Wikipedia search API for top 3 closest titles and suggests them. If completely unknown, returns a clean 404 error.

---

## 3. Storage & Deduplication

- **Content-Hash Zero-Compute Deduplication**:
  - Computes SHA-256 hash (`doc.content_hash`) over raw source text.
  - Queries Qdrant Cloud for Chunk 0's deterministic UUIDv5 ID before embedding.
  - Skips unchanged files with zero embedding latency (`Skipped N unchanged document(s)`).
- **Deterministic Point IDs**:
  - Every document receives a deterministic `page_id` (UUIDv5 of `source_uri`).
  - Every chunk receives `chunk_id = f"{page_id}-{chunk_index}"`.
  - Point ID in Qdrant is `uuid5(NAMESPACE_DNS, chunk_id)`:
    - Re-ingesting an updated file or directory overwrites existing points in-place idempotently without duplicating vectors or memory.
- Unified payload schema:
  - `chunk_id`: `str`
  - `doc_id`: `str`
  - `title`: `str`
  - `url`: `str` (`file:///...` or `https://...`)
  - `source_type`: `str` (`"markdown"`, `"pdf"`, `"code"`, `"table"`, `"audio"`, `"image"`, `"web"`, `"wiki"`)
  - `chunk_index`: `int`
  - `breadcrumb`: `str`
  - `text`: `str`
  - `content_hash`: `str`

---

## 4. Verification Gates (All Passed Live)

1. `ser add README.md` -> successfully extracts and chunks Markdown with heading breadcrumbs; deduplication verified on rerun.
2. `ser add 25-26_GEAR.pdf` -> layout-aware multi-column parsing with curriculum tables using `pymupdf4llm`.
3. `ser add scanned_report.pdf` -> `has_text_layer() -> False` detected; page-by-page OCR extracted text, retrieved at Rank #1.
4. `ser add test_audio.wav` -> `faster-whisper` transcribed speech with timestamps, retrieved at Rank #1.
5. `ser add test_shapes.png` -> `moondream` generated geometric scene descriptions, retrieved at Rank #1.
6. `ser add https://example.com` -> stripped web boilerplate and indexed prose, retrieved at Rank #1.
7. `ser add temp_mixed` -> processed mixed folder (`.py`, `.md`, `.csv`) in single batch run.
8. `ser add "Albert Einstein"` -> detects non-path, retrieves Wikipedia article live, and upserts.
9. `ser search "<query>"` -> displays results citing both Wikipedia and local files with clickable file links.
