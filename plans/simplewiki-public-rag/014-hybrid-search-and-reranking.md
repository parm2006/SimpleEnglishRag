# 014 — Hybrid Search (BM25 + Dense) and Cross-Encoder Re-Ranking

Status: COMPLETED. Dependencies: 006, 010.
Completed: Implemented sub-120ms hybrid search combining FastEmbed BM25 lexical scoring, Qdrant Cloud on-disk payload text indexing (`title`, `text`), and dense ONNX embeddings with Reciprocal Rank Fusion (RRF). Integrated optional INT8 ONNX Cross-Encoder re-ranker (`Xenova/bge-reranker-base`). Benchmark confirmed +6.2% recall boost (96.9% Hit@5) with negligible latency overhead (+23 ms).
Read handbook baseline/drift rules, ARCHITECTURE.md, and CONTRACTS.md.

## Outcome and Ownership

Own `src/ser/hybrid.py`, `src/ser/rerank.py`, `src/ser/db.py` (text indexes), `src/ser/pipeline.py` (candidate pool & routing), `src/ser/cli.py` (flags & animations), `src/ser/mcp_server.py` (tool toggles), and `src/ser/eval.py` (hybrid/rerank benchmarking).
Ensure all operations run with $O(1)$ memory, maintain sub-second response times, and preserve the cloud-first storage mandate without adding external databases.

---

## Architectural Decisions & Implementation

### 1. The Candidate Pool Architecture
- **Problem**: Earlier prototypes exposed candidate pool sizing or returned raw candidate counts instead of the requested $k$.
- **Solution**: Decoupled candidate retrieval from user/caller $k$. The pipeline always fetches an internal candidate pool of 15 points (via dense search or hybrid union), performs optional re-ranking, and then cleanly slices `[:k]`. This ensures the LLM or user always receives exactly top-$k$ results regardless of whether hybrid or re-ranking is active.

### 2. FastEmbed BM25 & Qdrant Payload Text Indexing
- **Sparse Vector Constraint**: Qdrant Cloud collections created without sparse vector configuration cannot add sparse vectors dynamically without full re-indexing of all 476,536 points.
- **Dual-Prong Solution**:
  1. **Server-Side Full-Text Payload Indexes**: Initialized `models.TextIndexParams(tokenizer=models.TokenizerType.WORD, lowercase=True, on_disk=True)` on both `title` and `text` fields in Qdrant Cloud. Enables exact and prefix keyword matching across the entire corpus.
  2. **FastEmbed BM25 Dynamic Scoring**: Loaded `Qdrant/bm25` locally. Computes exact lexical BM25 token frequencies across the candidate pool in ~4.9 ms on CPU without requiring an external Lucene or Elasticsearch cluster.

### 3. Reciprocal Rank Fusion (RRF)
- Merges ranked dense semantic candidates ($R_{\text{dense}}$) and ranked BM25 lexical candidates ($R_{\text{bm25}}$) into a unified score:
  $$\text{RRF\_Score}(d) = w_{\text{dense}} \cdot \frac{1}{k_{\text{rrf}} + \text{rank}_{\text{dense}}(d)} + w_{\text{bm25}} \cdot \frac{1}{k_{\text{rrf}} + \text{rank}_{\text{bm25}}(d)}$$
- Parameters:
  - $w_{\text{dense}} = 0.6$ (preserves high-level conceptual understanding)
  - $w_{\text{bm25}} = 0.4$ (boosts exact keyword and entity precision)
  - $k_{\text{rrf}} = 60$ (standard Cormack smoothing constant)

### 4. Cross-Encoder Re-Ranking (`Xenova/bge-reranker-base`)
- **Model**: Local INT8 ONNX quantized cross-encoder loaded via FastEmbed `TextCrossEncoder`.
- **Optimization**: Dynamic token padding via `tokenizer.enable_padding()` and truncated `max_length=256` to avoid $O(L^2)$ transformer attention overhead.
- **Latency**: ~2,257 ms on multi-core CPU across 15 candidates.
- **Topical Distraction Analysis**:
  - Evaluation revealed cross-encoder re-ranking slightly decreased MRR (0.795 $\to$ 0.759) and displaced certain target articles (e.g., *Mariana Trench* displaced by *2011 Pacific typhoon season*).
  - Cause: Cross-encoders compute token-to-token cross-attention, heavily favoring exact surface keywords that appear in unrelated historical or geographical narratives, whereas bi-encoder dense vectors represent the holistic conceptual topic of the chunk.
  - Decision: Keep dense/hybrid search as the fast, sub-second default; keep cross-encoder as an explicit, opt-in toggle (`--rerank`).

---

## Benchmark Results (32 Canonical Queries, $k=5$)

| Strategy | Hit @ 1 | Hit @ 3 | Hit @ 5 (Recall) | MRR | Latency (p50) |
|---|:---:|:---:|:---:|:---:|:---:|
| **Dense Vector (Baseline)** | **71.9%** | 84.4% | 90.6% | 0.795 | **91 ms** |
| **Hybrid (Dense + BM25 + Text)** | 68.8% | **90.6%** (+6.2%) | **96.9%** (+6.2%) | **0.802** | **114 ms** (+23 ms) |
| **Cross-Encoder Re-ranking** | 65.6% | 84.4% | 90.6% | 0.759 | 2,257 ms |

- **Key Rescue**: Hybrid search rescued two queries that failed completely in pure vector search:
  - *Subduction* (Tectonic plates): Miss $\to$ Rank #3
  - *Dead Sea* (Lowest land elevation): Miss $\to$ Rank #4

---

## Verification Gates

1. **CLI Flag Tests**:
   - `ser search "subduction" --hybrid` returns Rank #3 with RRF score.
   - `ser search "subduction" --rerank` executes cross-encoder re-ranking.
   - `ser ask "What is subduction?" --hybrid` streams Ollama cited answer.
2. **MCP Tool Integration**:
   - `search_wikipedia(query, k, hybrid=True, rerank=False)` verified in Model Context Protocol inspector.
3. **Database Health**:
   - `ser stats` verifies payload text indexes active and collection status `green`.
