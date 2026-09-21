# 002 — Prove Python and browser embeddings agree

Status: COMPLETED (FastEmbed ONNX Vector Engine). Dependency: 001.
Completed: `BAAI/bge-small-en-v1.5` (384-dimensional dense vectors) implemented in `src/ser/embed.py` using FastEmbed with ONNX Runtime CPU acceleration and PyTorch CUDA GPU support on Colab. Browser embeddings dropped with UI pivot.
Read ARCHITECTURE.md, CONTRACTS.md and SOURCES.md.

## Outcome and ownership

Own config/embedding.json, src/simplewiki/embed.py (model adapter only), packages/embedding/src/{embed,tokenize,config}.ts, scripts/{embedding-reference.py,embedding-parity.mjs}, tests/fixtures/embedding/, tests/unit/test_embedding_input.py, reports/embedding-parity.md. Package/lock edits only to add required model dependencies, coordinated with owner.

A pinned browser query model must retrieve against Python document embeddings. A matching vector length alone is not success.

## Steps

1. Resolve exact immutable commit revisions for BAAI and Xenova repositories and save them. Inspect tokenizer, special tokens, maximum length and pooling config. Verify conversion provenance and model license. Record downloaded filenames and SHA-256 values; trust_remote_code=false in Python.
2. Freeze CLS pooling, L2 normalization, query prefix and document formatting from CONTRACTS.md. The ONNX card's mean pooling snippet is not the intended contract. Inspect actual first-token output and tests rather than changing Python to imitate that snippet.
3. Prepare 40 hand-authored short passages across at least 8 topics and 20 questions with expected passages. Include dates, proper nouns, punctuation, non-ASCII titles, newlines, empty/whitespace input, and text at 479/480/481 input tokens. Keep synthetic fixtures small and reproducible.
4. Implement Python encode_documents and encode_queries wrappers using CPU SentenceTransformer. Assert dimensions, finite values and unit norm. Enforce exact input length before inference. No silent truncation. Include matching tokenization fixture outputs.
5. Implement reusable TS embedding adapter with browser-compatible WASM baseline; choose explicit device/dtype and CLS pooling. First run fp32 conversion. Do not require WebGPU. Use the same adapter later from a browser Web Worker; keep it independent of React.
6. Produce Python reference vectors locally. Compare identical Python/JS input token IDs and special tokens. For fp32, require per-vector cosine >=0.999 on nonempty fixtures and same expected top result on unambiguous questions. Investigate ties individually.
7. Test q8. Require per-vector cosine >=0.98 relative to Python and at least 90% overlap between reference and q8 top-five sets across questions, plus no loss of expected-passage Hit@5 on this fixture. These are initial project gates, not scientific guarantees; real corpus eval follows.
8. If q8 fails, use fp32 only when the owner accepts measured download/latency; do not lower gates silently. If fp32 fails, stop and resolve tokenizer/pooling/model mismatch before continuing.
9. Run adapter in a real Chromium browser on WASM, not just Node. Record cold model transfer bytes, cached load, first/warm query times and memory symptoms on the owner's computer. Initial goals: cold start within 60 seconds on recorded connection; warm embedding p95 <3 seconds on recorded desktop. Report slower mobile results honestly.
10. Compute embedding_contract_id only after choices pass. Keep exact revision/dtype/pooling/checksums in config; downstream jobs must compare this ID before reuse. Separate fixture generation (--prepare, may download) from --offline verification. Add npm run test:embedding and a documented manual browser probe.

## Verification gates

- uv run pytest tests/unit/test_embedding_input.py
- npm run test:embedding -- --prepare (first preparation only; creates ignored local model/reference artifacts)
- npm run test:embedding -- --offline
- npm run typecheck
- Real Chromium probe uses the same TS adapter and all 20 questions; save measured report.

Expected: deterministic fixture results, correct error for empty/oversized input, pinned revisions, no downloads during offline check. Fail test when query prefix or pooling is deliberately changed, then revert the deliberate change.

## Completion and STOP

Report actual bytes, dtype, model revisions, token agreement, minimum cosine, retrieval overlap and latency. These exact config values replace provisional assumptions for later plans.
STOP on parity failure, unavailable artifacts, or unacceptable required browser download. Hand back evidence; do not embed the corpus first.

