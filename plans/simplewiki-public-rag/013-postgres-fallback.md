# 013 — Conditional full-corpus Postgres + pgvector fallback

Status: DROPPED / UNNECESSARY. Dependencies: None.
Decision: Trigger condition was not met. Qdrant Cloud Free Tier comfortably holds and serves the complete 245,375-point corpus with INT8 scalar quantization and on-disk payload indexing, keeping RAM footprint under limits without Postgres.
Read handbook, ARCHITECTURE.md, and CONTRACTS.md.

## Outcome and ownership

Own src/simplewiki/stores/postgres.py, SQL migrations/, Postgres integration tests, conditional local API/public deployment adapter, compose postgres profile, reports/postgres-capacity.md.
Reuse existing corpus chunks and vectors. Do not build or maintain a second production backend unless this trigger occurs.

## Hosting reality first

Postgres is free software, not automatically free hosted storage. At execution compare candidate hosts' actual database/index/WAL/backup space, pgvector support/version, memory, connection limits, egress, inactivity and region against measured corpus. Do not invent a provider, fixed current quota or working Cloudflare-to-Postgres connection method.

Prove local correctness/capacity first. Before hosted deployment, record the selected provider and connection interface in memo-postgres-hosting.md. If no free host fits, the owner chooses paid hosting or postpones public full-corpus deployment. Local-only operation does not satisfy the public-link requirement.

## Steps

1. Add pinned Postgres image and pgvector extension version to optional Compose profile, localhost port and separate named volume. Keep existing Qdrant data.
2. Create migrations with extension vector and chunks table: chunk_id UUID PK, corpus_id text, page/revision IDs text, title/section/text/URLs/license, embedding vector(384). Add unique/current-corpus constraints and B-tree lookup indexes. No public anonymous SQL privileges.
3. Implement parameterized bulk COPY from existing JSONL/.npy artifacts into a staging corpus/table. Validate row/vector order and finite unit vectors. Commit batches/checkpoint transactionally; resume deterministic UUID upserts through a safe staging merge.
4. Start with exact cosine search as correctness baseline:
ORDER BY embedding <=> query_vector LIMIT 24, with corpus filtering.
Use parameterized values and fixed table identifiers, never interpolated user input.
5. Build HNSW with vector_cosine_ops after bulk load. Measure graph build peak memory/disk and choose settings from actual capacity. Consider halfvec only as a separately evaluated representation; don't change artifact contract.
6. Implement SearchStore.search with same top24, max2/page, limit<=8 and payload shape. Reuse public conformance fixtures; scores map to 1 - cosine distance for consistent rank direction.
7. Reconcile all expected chunk UUIDs and compare sampled content/vector values. Run same held-out question/browser vectors; target same quality and latency as 010. Compare ANN results to exact baseline; HNSW filtering/candidate limits may reduce recall, so measure rather than assume.
8. Measure heap, TOAST, indexes, WAL, temporary build files, backups and resident memory. Use pg_total_relation_size plus storage-level metrics, not raw vector multiplication alone. Make full-corpus fit report and space reserve.
9. Hosting branch: preserve /api/config and /api/search. If selected provider offers a suitable serverless driver/HTTP interface, implement fixed parameterized queries behind Worker. If normal Postgres connections require a Python service, use the local FastAPI adapter as hosted search service with rate limits and same-origin routing/reverse proxy; this hosting change needs the recorded memo. Do not expose Postgres credentials or unrestricted SQL/RPC to browser.
10. Database roles: operator may migrate/import; search role can only select required data or execute narrow search function. If a database function is exposed, cap limit and input and lock search_path/privileges. Frontend never receives service-role credentials.
11. Provision a new database, import and verify before changing active service. Run 011 public acceptance against Postgres path; preserve old Qdrant until rollback decision. Backups via portable artifacts plus pg_dump/restore practice on a disposable local database.
12. Update deployment tuple/config, supported backend docs and plan index. Do not delete other backend artifacts by default.

## Verification gates

- uv run pytest tests/integration/test_postgres.py
- Public API conformance suite runs against Postgres adapter.
- uv run simplewiki evaluate --build data/builds/full --backend postgres --questions tests/eval/questions-full.jsonl --output reports/retrieval-postgres.json
- Full count/ID/content reconciliation and measured capacity report.
- Disposable database backup/restore test and public second-device test when hosted.

## Completion and STOP

DONE requires a measured selected backend; local proof may be recorded separately while hosting is BLOCKED.
STOP if hosting quota/driver/permissions are unresolved, migration is destructive, or paid service is required. Hand back concrete sizes and provider options, never silently prune corpus or weaken the search role.
