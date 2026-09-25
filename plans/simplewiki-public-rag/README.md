# `ser` (Simple English RAG) — Master Plan & Implementation Status

## 1. Project Overview & Core Architecture

`ser` is a **modular, local-first RAG engine and system-wide CLI**, designed for local AI agents, subagents, and command-line research.
- **Vectors**: FastEmbed ONNX `BAAI/bge-small-en-v1.5` (384 dimensions) running locally on CPU in ~2–5 ms.
- **Storage**: Qdrant Cloud (`simple_wiki` collection) with INT8 scalar quantization (4x RAM reduction) and on-disk payloads.
- **Generation**: Local Ollama (`llama3.2:3b`, `qwen2.5:3b`, `qwen2.5:1.5b`) with strict `[1]`, `[2]` citation grounding.
- **Vision**: Local multimodal inference via `moondream` with hardware-accelerated Windows Media OCR (`winsdk`) fallback.
- **Audio**: Lazy-loaded `faster-whisper` (`tiny.en`, INT8) transcribing speech into timestamped chunks.
- **Global Executable**: `ser` (installed via `uv tool install --editable --with faster-whisper .`).

---

## 2. Master Feature Status

| Component / Feature | Roadmap / Plan | Status | Details |
|---|---|:---:|---|
| **Modular Engine Architecture (`ser`)** | Phase 1 | ✅ **Done** | Decoupled ingest, chunk, embed, points, db, pipeline, generate, and cli modules. |
| **Qdrant Cloud Storage** | Phase 1 | ✅ **Done** | Hosted cluster, INT8 scalar quantization (4x RAM reduction), on-disk payload (476k+ points). |
| **FastEmbed ONNX Embeddings** | Phase 1 | ✅ **Done** | `BAAI/bge-small-en-v1.5` (384 dimensions) running locally on CPU. |
| **High-Speed Dump Streamer** | Plan 003 | ✅ **Done** | $O(1)$ memory XML.bz2 parser (~1,000 pages/sec) with atomic JSON checkpointing. |
| **Live Wikipedia Ingestion** | Phase 1 | ✅ **Done** | `ser ingest-wiki "<title>"` fetches, chunks, embeds, and uploads live articles in 1.5 seconds. |
| **Local Ollama Cited Generation** | Phase 2 | ✅ **Done** | Streaming generation with strict `[1]`, `[2]` citations, source references table, and 0.40 confidence guardrail. |
| **Global CLI & Interactive REPL** | Phase 3 | ✅ **Done** | Installed globally (`ser`), callable from any directory on the PC. |
| **MCP Server (Model Context Protocol)** | Expansion | ✅ **Done** | Exposes `search_wikipedia`, `ask_wikipedia`, and `index_article` to Google Antigravity, Claude, and Cursor. |
| **Evaluation Suite (`eval.py`)** | Phase 4.2 | ✅ **Done** | Automated benchmark: **100% Hit@5**, **86.7% Hit@1**, **0.9150 MRR**, **98.7 ms p50 latency** across 30 domains. |
| **Hybrid Search (Dense + BM25)** | Plan 014 | ✅ **Done** | FastEmbed BM25 + Qdrant Cloud on-disk payload text index + RRF fusion (+6.2% recall, 114 ms latency). |
| **Universal Ingestion (`ser add`)** | Plan 015 | ✅ **Done** | Polymorphic zero-flag ingestion for Markdown, code, CSV tables, digital/scanned PDFs, audio (`faster-whisper`), images (`moondream` / Windows OCR), web URLs, and Wikipedia articles. |
| **Content-Hash Deduplication** | Plan 015 | ✅ **Done** | SHA-256 document hashing + Qdrant Chunk-0 UUIDv5 probe, skipping unchanged documents with zero compute. |
| **AST-Based Code Chunking** | Plan 016 | ✅ **Done** | Standard library `ast.parse` for atomic Python function/class extraction; clean file-breadcrumb text fallback for non-Python codebases. |

---

## 3. Retained Active Plans

- [`001-foundation.md`](001-foundation.md): Foundation architecture and layout.
- [`002-embedding-proof.md`](002-embedding-proof.md): FastEmbed ONNX validation.
- [`003-download-and-extract.md`](003-download-and-extract.md): Stream ingestion of Wikipedia XML dumps.
- [`004-chunks-and-corpus.md`](004-chunks-and-corpus.md): Heading-aware text hierarchy chunking.
- [`005-embedding-artifacts.md`](005-embedding-artifacts.md): Batch embedding pipelines.
- [`006-qdrant-and-evaluation.md`](006-qdrant-and-evaluation.md): Qdrant schema & indexing.
- [`009-cited-answers.md`](009-cited-answers.md): Ollama grounded citation generation.
- [`010-full-corpus-and-capacity.md`](010-full-corpus-and-capacity.md): Full 476k+ chunk corpus capacity & quantization.
- [`012-local-offline-edition.md`](012-local-offline-edition.md): Local SSD embedded database (`QDRANT_STORAGE=local`).
- [`014-hybrid-search-and-reranking.md`](014-hybrid-search-and-reranking.md): Dense + BM25 reciprocal rank fusion & cross-encoders.
- [`015-universal-ingestion.md`](015-universal-ingestion.md): Polymorphic multi-format ingestion, audio, vision, PDFs, tables, deduplication.
- [`016-ast-code-chunking.md`](016-ast-code-chunking.md): Python AST atomic code chunking.
