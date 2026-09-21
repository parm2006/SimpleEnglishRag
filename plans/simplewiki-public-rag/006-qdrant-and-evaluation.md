# 006 — Local Qdrant index, search and retrieval evaluation

Status: TODO. Dependencies: 004,005. Suggested executor: Terra.
Read handbook baseline/drift rules, ARCHITECTURE.md and CONTRACTS.md. Inspect model, artifact and test exemplars.

## Outcome and ownership

Own src/simplewiki/{index,evaluate}.py, stores/{base,qdrant}.py, search/index/evaluate CLI commands, tests/integration/test_qdrant.py, tests/eval/{questions.jsonl,README.md}, reports/retrieval-baseline.md.
Use a real local Qdrant server, not only in-memory client mode.

## Steps

1. Start pinned server using docker compose up -d qdrant. Check reachable loopback endpoint and version. Build integration fixture with unique test collection name; teardown may delete only that exact newly created test collection. Tests must reject cloud URLs.
2. Create physical corpus-specific collection: 384-dim cosine, one shard, replication one, on-disk vectors and payloads. Use on-disk HNSW if supported by locked server; verify generated config via API. Start with defaults for index graph quality, no quantization.
3. Import chunk/vector shards by UUID using bounded batches (default 128 points, cap serialized bytes). wait=true before checkpointing. Persist acknowledged shard/batch progress. Retrying an interrupted batch is safe because IDs are deterministic.
4. Existing collection must match corpus, embedding contract and dimensional settings. Never delete/recreate a populated collection implicitly. Store an external deployment manifest binding collection and corpus. Before public use sample-check every payload contract and verify exact point count.
5. Reconcile all expected IDs using counts plus sorted/streamed ID digest; counts alone cannot detect missing-and-extra pairs. Verify sampled vector cosine/metadata against local artifacts. No indexing of checkpoint metadata as a fake content point.
6. Implement SearchStore.search and CLI search --build <path> --query <text> --limit 5. Embed query using exact contract. Query top 24, deterministic tie-break, max two per page. Show text/title/section/source URL; optional --json emits public result shape.
7. For bulk jobs, if temporarily disabling HNSW indexing is beneficial, save original settings and restore them in a finalization step even after retries. Completion requires optimizer/index ready and no error state; an accepted upload alone is not a ready index.
8. Create 60 reviewed evaluation questions: 40 answerable factual/explanatory, 10 exact names/dates, 10 unanswerable/out-of-scope. Split 20 development and 40 held-out before tuning. Label acceptable page IDs and supporting passages from actual selected corpus. Synthetic questions and real corpus questions are separate suites.
9. Evaluate candidate Hit@5 (at least one relevant article), MRR@10 on raw ranked candidates and final displayed Hit@5 after diversity filtering. Record question IDs and exact corpus/model IDs. Run browser query vectors from 002 against the same index to catch cross-runtime degradation.
10. Initial release gate: displayed Hit@5 >=85% of answerable held-out questions, with no major topic category completely failing. This is a small-set target, not an accuracy claim. Failures drive cleaning/chunk/model investigation. Keep held-out set out of tuning; add new test questions if tuning exhausts it.
11. Unanswerable questions may still return closest passages; search must not claim it found an answer. Generation refusal is evaluated in 009.
12. Measure warmed search latency and separate embedding time. Use 1 and 5 concurrent local clients for 100 queries; log p50/p95, errors and environment. Initial target search p95 <=2 seconds, error rate <1%; record rather than hide slow results.
13. Implement verify --finalize --evaluation PATH --audit PATH per CONTRACTS.md. Own schemas/audit.schema.json and src/simplewiki/manifest.py extensions for this step. Audit fields: corpus_id, reviewed page IDs, reviewer, review date, unresolved issue count and approved boolean. Define matching versioned evaluation report schema with corpus/model IDs, question-set hash, split, metrics and gate results. Require owner-recorded audit and passing matching evaluation before ready. Sample and full builds use identical integrity rules; scope remains explicit. Add unit tests refusing stale report IDs, failed gates and missing audit.

## Verification gates

- docker compose up -d qdrant
- uv run pytest tests/integration -m qdrant
- uv run simplewiki index --build data/builds/sample-1000 --url http://127.0.0.1:6333
- uv run simplewiki search --build data/builds/sample-1000 --query "Why do plants need sunlight?" --limit 5
- uv run simplewiki evaluate --build data/builds/sample-1000 --questions tests/eval/questions.jsonl --output reports/retrieval-baseline.json

Sample-specific evaluation labels must point to pages present in sample; CLI fails on missing expected pages instead of counting them as retrieval failure. Default tests do not contact cloud.

## Completion and STOP

Report counts, ID reconciliation, metrics and inspection of displayed passages. Mark any unrun real-index or browser-vector check explicitly.
STOP on unexplained missing data, model mismatch or failed quality gate. No cloud upload in this plan.
