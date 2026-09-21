# Agent Guidelines for `ser` (Simple English RAG)

This document provides explicit instructions for AI Agents, autonomous coding assistants, and subagents interacting with this repository or using `ser` as an external tool.

---

## 1. Fast Overview

`ser` is a local-first RAG engine providing sub-second semantic retrieval across the Simple English Wikipedia corpus.
- **Vectors**: FastEmbed ONNX `BAAI/bge-small-en-v1.5` (384 dimensions).
- **Storage**: Qdrant Cloud (`simple_wiki` collection) with INT8 scalar quantization.
- **Generation**: Local Ollama (`llama3.2:3b`, `qwen2.5:3b`, etc.) with strict `[1]`, `[2]` citation grounding.
- **Global Executable**: `ser` (installed via `uv tool install --editable .`).

---

## 2. Using `ser` from Subshells & Command Tools

When performing research or answering questions within agent workflows, you can execute `ser` commands directly:

### A. Semantic Search Only (Fastest, No LLM Required)
```bash
ser search "<query>"
# Or with hybrid dense + BM25 fusion
ser search "<query>" --hybrid
# Or with cross-encoder re-ranking
ser search "<query>" --rerank
```
- **Returns**: Top passages with title, similarity score (Cosine / RRF / Re-rank), URL, and chunk text.
- **Latency**: < 100 ms for vector search; ~114 ms for hybrid search; ~2s for cross-encoder.
- **Recommended for**: Gathering background facts, verifying claims, finding source citations.

### B. Full RAG Question Answering (Requires Local Ollama)
```bash
ser "<question>"
# or
ser ask "<question>" [--hybrid] [--rerank]
```
- **Returns**: Formatted answer with `[1]`, `[2]` footnote markers and a citations table.
- **Guardrail**: Automatically returns `"I could not find sufficient information..."` if top similarity score is below `0.40`.

### C. Check Cluster Health & Point Count
```bash
ser stats
```
- **Returns**: Storage mode (`CLOUD`), Points count, status (`green`), vector dimension, and quantization.

### D. Index New Articles Live
```bash
ser ingest-wiki "<Article Title>"
```
- Fetches article prose from Wikipedia Action API, splits into ~1,200 character chunks, generates vectors, and upserts to Qdrant Cloud.

---

## 3. Python API Integration

If the agent is executing Python code in an environment or sandbox, invoke the internal API directly:

```python
from ser.db import client
from ser.pipeline import ask
from ser.generate import generate_answer

# Step 1: Retrieve top-k scored chunks (optional hybrid and rerank)
query = "What is gravity?"
chunks = ask(client, query=query, k=3, hybrid=True, rerank=False)

for point in chunks:
    title = point.payload.get("title")
    url = point.payload.get("url")
    text = point.payload.get("text")
    score = point.score
    print(f"[{score:.4f}] {title} ({url}):\n{text}\n")

# Step 2: (Optional) Grounded generation with Ollama
answer, citations = generate_answer(query, chunks)
print("Answer:", answer)
```

### Point Payload Schema
Each point yielded by `ask()` is a `qdrant_client.models.ScoredPoint`:
- `point.id`: `str` (UUIDv5 derived from `chunk_id`)
- `point.score`: `float` (Cosine similarity, typically `0.60`–`0.85` for relevant hits)
- `point.payload`: `dict` containing:
  - `"chunk_id"`: `str` (`"{doc_id}-{chunk_index}"`)
  - `"doc_id"`: `str` (Wikipedia Page ID)
  - `"title"`: `str` (Article title)
  - `"url"`: `str` (Wikipedia URL)
  - `"chunk_index"`: `int` (Index within article)
  - `"text"`: `str` (Passage text)
  - `"breadcrumb"`: `str` (Section hierarchy path e.g. `"Apollo 11 > The Flight"`)

---

## 4. Environment Variables (`.env`)

Agents modifying or launching services should be aware of these configuration keys:

| Variable | Default | Purpose |
|---|---|---|
| `QDRANT_STORAGE` | `cloud` | `cloud`, `local`, or `memory` |
| `QDRANT_URL` | N/A | Qdrant Cloud cluster endpoint |
| `QDRANT_API_KEY` | N/A | Qdrant Cloud API authentication token |
| `QDRANT_COLLECTION`| `simple_wiki` | Collection name in Qdrant |
| `OLLAMA_HOST` | `http://localhost:11434` | Local Ollama endpoint |
| `OLLAMA_MODEL` | Auto-detected | Preferred generation model (`llama3.2:3b`, `qwen2.5:3b`) |
| `CONFIDENCE_THRESHOLD` | `0.40` | Minimum similarity score required for generation |

---

## 5. Coding Standards & Maintenance

- **Never re-add local vector storage**: All vectors must live in Qdrant Cloud per user mandate. Do not create local SQLite or vector directories.
- **Windows UTF-8**: Ensure console stdout encodes in `utf-8` to prevent `cp1252` encoding errors on non-ASCII characters.
- **Resilient Upserting**: Any code calling `client.upsert` must use the retry wrapper in `src/ser/db.py` to prevent batch job failures from network blips.
- **Deterministic Deduplication**: Always use `uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id)` for point IDs so re-ingesting content updates in-place idempotently.

---

## 6. Understanding Qdrant Status & Relevance Colors

When evaluating cluster health or search scores:

### A. Cluster Health Status (`ser stats`)
- **`green`**: Fully healthy. All vector shards, HNSW graphs, and INT8 scalar quantization indexes are synchronized and ready for queries.
- **`yellow`**: Optimizing. Background segment merging, WAL vacuuming, or quantization indexing is running. Queries still succeed.
- **`red`**: Degraded/Down. One or more shards are unavailable. Queries may fail or return partial results.

### B. Similarity Score Thresholds (`ser search`)
- 🟢 **Green (`>= 0.70`)**: High semantic confidence. Strong factual relevance.
- 🟡 **Yellow (`0.50` to `0.69`)**: Moderate relevance. Adjacent or topical background context.
- 🔴 **Red (`< 0.50`)**: Low confidence. If top score is `< 0.40`, generation is aborted by anti-hallucination guardrail.
