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
| **1-Click Colab GPU Ingestion** | Bonus | ✅ **Done** | [`colab_ingest.ipynb`](../../colab_ingest.ipynb) for 15-minute free T4 GPU ingestion. |
| **Comprehensive Documentation** | Showcase | ✅ **Done** | Root [`README.md`](../../README.md) and [`AGENTS.md`](../../AGENTS.md) with architecture diagrams and API specs. |
| **Core Knowledge Base Ingestion** | Active | ✅ **12,671 Chunks** | 2,700 foundational articles (Science, History, Computing, Math, Philosophy) live in Qdrant Cloud. |
| **Full Corpus Colab GPU Execution** | Active | ⏳ **In Progress** | Running `colab_ingest.ipynb` to complete the remaining ~235k articles. |
| **Evaluation Suite (`eval.py`)** | Phase 4.2 | ⏳ **TODO** | Automated benchmark measuring Hit Rate @ k, MRR, and p50/p95 latency across canonical test queries. |
| **MCP Server (Model Context Protocol)** | Expansion | ⏳ **TODO** | FastMCP server exposing `search_wikipedia`, `ask_wikipedia`, and `index_article` to Claude Desktop & Cursor. |
| **Hybrid Search (Dense + BM25)** | Phase 4.1 | ⏳ **TODO** | FastEmbed BM25 sparse vectors paired with dense vectors via Reciprocal Rank Fusion (RRF). |
| **Universal Ingestion ("Ingest Anything")**| Phase 3.2 | ⏳ **TODO** | Ingestion source adapters for local PDFs, Markdown vaults, and plain text folders. |

---

## 3. Active Next Priorities

1. **Colab GPU Full Dump Ingestion**: Complete the remaining Wikipedia dump into Qdrant Cloud via free T4 GPU.
2. **Evaluation Suite (`eval.py`)**: Build and run an evaluation benchmark on the Qdrant Cloud collection.
3. **MCP Server**: Implement the FastMCP server for Claude Desktop / Cursor integration.
