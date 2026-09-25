# `ser` (Simple English RAG) — Master Plan & Implementation Status

## 1. Project Pivot & Core Focus

This project originated as a planned public web application (`simplewiki-public-rag`). It has successfully pivoted into a **modular, local-first Python RAG engine and system-wide CLI named `ser`**, designed for local AI agents, subagents, and command-line research.

### Explicitly Dropped / Out of Scope
Per explicit user decisions, the following originally planned components have been **permanently dropped**:
- ❌ **Web Frontend / UI (Plan 008)**: Dropped. No web browser UI is needed; `ser` is a local CLI and Python library.
- ❌ **Public Search REST API / Cloudflare Worker (Plans 007, 011)**: Dropped. No public web API or Cloudflare deployment is needed.
- ❌ **Phase 2.2 Cloud LLM Fallbacks (Groq, Gemini, DeepSeek)**: Dropped. Local Ollama (`llama3.2:3b`, `qwen2.5:3b`) is the dedicated, private generation engine.
- ❌ **Postgres / pgvector Fallback (Plan 013)**: Dropped. Qdrant Cloud Free Tier with INT8 scalar quantization successfully holds the corpus without memory exhaustion.

---

## 2. Recompiled Master Feature Status

| Component / Feature | Roadmap / Plan | Status | Details |
|---|---|:---:|---|
| **Modular Engine Architecture (`ser`)** | Phase 1 | ✅ **Done** | Decoupled ingest, chunk, embed, points, db, pipeline, generate, and cli modules. |
| **Qdrant Cloud Migration** | Phase 1 | ✅ **Done** | Hosted cluster, INT8 scalar quantization (4x RAM reduction), on-disk payload. Local vector dirs deleted. |
| **FastEmbed ONNX Embeddings** | Phase 1 | ✅ **Done** | `BAAI/bge-small-en-v1.5` (384 dimensions) running locally on CPU. |
| **High-Speed Dump Streamer** | Plan 003 | ✅ **Done** | $O(1)$ memory XML.bz2 parser (~1,000 pages/sec) with atomic JSON checkpointing (`data/ingest_checkpoint.json`). |
| **Live Wikipedia Ingestion** | Phase 1 | ✅ **Done** | `ser ingest-wiki "<title>"` fetches, chunks, embeds, and uploads live articles in 1.5 seconds. |
| **Local Ollama Cited Generation** | Phase 2 | ✅ **Done** | Streaming generation with strict `[1]`, `[2]` citations, source references table, and 0.40 confidence guardrail. |
| **Global CLI & Interactive REPL** | Phase 3 | ✅ **Done** | Installed globally (`ser`), callable from any directory on the PC. |
| **1-Click Colab GPU Ingestion** | Bonus | ✅ **Done** | [`colab_ingest.ipynb`](../../colab_ingest.ipynb) & [`colab_standalone.ipynb`](../../colab_standalone.ipynb) for fast T4 GPU ingestion. |
| **Comprehensive Documentation** | Showcase | ✅ **Done** | Root [`README.md`](../../README.md) and [`AGENTS.md`](../../AGENTS.md) with architecture diagrams and API specs. |
| **Core Knowledge Base Ingestion** | Phase 1 | ✅ **Done** | 2,700 foundational articles (Science, History, Computing, Math, Philosophy) ingested locally. |
| **Full Corpus Colab GPU Execution** | Phase 1 | ✅ **410,000+ Chunks** | Ingested via [`colab_standalone.ipynb`](../../colab_standalone.ipynb) on T4 GPU into Qdrant Cloud. Status: `green`. |
| **MCP Server (Model Context Protocol)** | Expansion | ✅ **Done** | [`src/ser/mcp_server.py`](../../src/ser/mcp_server.py) exposing `search_wikipedia`, `ask_wikipedia`, and `index_article` to Google Antigravity, Claude Desktop, and Cursor. |
| **Evaluation Suite (`eval.py`)** | Phase 4.2 | ✅ **Done** | Automated benchmark: **100% Hit@5**, **86.7% Hit@1**, **0.9150 MRR**, **98.7 ms p50 latency** across 30 domains. |
| **Hybrid Search (Dense + BM25)** | Plan 014 | ✅ **Done** | FastEmbed BM25 + Qdrant Cloud on-disk payload text index + RRF fusion (+6.2% recall, 114 ms latency). |
| **Universal Ingestion (`ser add`)**| Plan 015 | ✅ **Done** | Polymorphic zero-flag ingestion for local Markdown, code, PDFs (`pymupdf4llm`), web URLs, and Wikipedia articles with nearest-match fallback and content_hash dedup. |
| **AST-Based Code Chunking** | Plan 016 | 🔄 **In Progress** | Syntax-aware atomic chunking for Python (`ast`) and polyglot codebases (`.rs`, `.ts`, `.go`, `.cpp`) with function/class breadcrumbs. |

---

## 3. Active Next Priorities

1. **Plan 016 (AST Code Chunking)**: Implementing `src/ser/ingest/chunk_code.py` using Python's standard library `ast` module to eliminate severed functions and orphan code signatures.
2. **Continuous Expansion & Evaluation**: Benchmarking retrieval accuracy across codebases, technical documentation, and mixed-format local vaults.


