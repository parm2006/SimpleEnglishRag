# 010 — Full-corpus build and measured storage decision

Status: TODO. Dependencies: 003..006; browser parity from 002. Can run before UI plans finish.
Suggested executor: Terra for automation; owner supervises resource decisions.
Read handbook, ARCHITECTURE.md capacity policy and CONTRACTS.md. This plan explicitly covers full source processing after fixture gates.

## Outcome and ownership

Own src/simplewiki/capacity.py, capacity/verify CLI extensions, scripts/benchmark-search.py, tests/unit/test_capacity.py, docs/capacity.md, reports/capacity-*.json, ignored data artifacts.
Determine whether ALL eligible articles fit free Qdrant, using evidence.

## Steps

1. doctor checks available disk/RAM, model cache, Docker and paths. Establish actual peak local disk budget for compressed dump, extracted shards, SQLite, vectors, Qdrant and backups. Do not promise a fixed small footprint. Stop cleanly if estimated required free space is absent.
2. Download/check source from 003. Stream all pages through extraction/chunking. Save complete accounting and final chunk count. Full articles must be processed even if browser release initially uses sample corpus.
3. Review audit: page dispositions total equals input pages; zero unexplained main-namespace failures; redirects/empty flagged; eligible nonempty article count equals distinct chunk page count. Publish extraction limitations separately, including unknown templates and images not included.
4. Run deterministic 10,000-article representative sample plus separate stress sample. Embed/index and wait for optimizer settling before measuring. Do not extrapolate from compressed dump size or first few articles.
5. Measure raw vectors, payload JSON bytes, SQLite bytes, indexed Qdrant disk, resident memory and peak indexing disk. For preliminary projection, calculate fixed overhead plus variable bytes/chunk times actual full chunk count; record pessimistic headroom factor 1.5 for unmeasured transient overhead. State uncertainty.
6. If preliminary fit plausible, embed full corpus with resumable shards. Estimate completion time from sample chunks/sec; bound CPU/GPU batch memory. Monitor progress and disk; interruption resumes at verified shards.
7. Index full corpus locally. Emulate intended on-disk settings and 1 GB RAM/0.5 CPU constraints where Docker supports limits; document when local simulation differs from cloud. Do not create snapshots inside near-full constrained volume without checking space.
8. Run full ID digest reconciliation and sampled text/vector integrity. Inspect ready status. Calculate steady-state/peak headroom against actual cloud quota from account.
9. Re-evaluate real corpus with held-out questions and browser query vectors. Extra articles can change ranking; sample metrics are not release metrics. Initial targets: Hit@5 >=85%, warmed search p95 <=2 sec with 5 concurrent clients, <1% errors, disk/RAM headroom from architecture.
10. If memory fails but disk fits, try on-disk HNSW/vector/payload configuration. Record config before/after. If quantization is tested, measure actual disk and quality; don't assume deleting original vectors is safe or supported. Require <=2 percentage-point Hit@5 regression and same latency gate.
11. If all eligible text still cannot fit, produce explicit no-go for Qdrant free and invoke conditional plan 013. Do not remove chunks/articles, split collections hoping quota grows, or violate 480-token input cap.
12. Use verify --finalize --evaluation PATH --audit PATH from 006 to produce release manifest ready only after final artifacts, counts, model/corpus-matched quality report and owner-recorded extraction audit pass. Portable snapshot is optional optimization; original SQLite/JSONL/.npy must remain rebuildable without snapshot compatibility.
13. Record a comparison report: corpus date, total pages/articles/chunks, ignored reasons, vector dimension, bytes per layer, peak disk/RAM, machine, latency, browser test, model contract, chosen backend and free-tier decision.

## Verification gates

- uv run pytest tests/unit/test_capacity.py
- uv run simplewiki verify --build data/builds/full
- uv run simplewiki capacity --build data/builds/full --output reports/capacity-full.json
- uv run simplewiki evaluate --build data/builds/full --questions tests/eval/questions-full.jsonl --output reports/retrieval-full.json
- uv run python scripts/benchmark-search.py --build data/builds/full --concurrency 5 --requests 100
- uv run simplewiki verify --build data/builds/full --finalize --evaluation reports/retrieval-full.json --audit reports/extraction-audit-full.json

capacity must distinguish measured fields from projections. Full verify checks all IDs/counts and artifact hashes; performance doesn't excuse missing articles.

## Completion and STOP

Outcome is GO Qdrant free or NO-GO with evidence and 013 next. A failed capacity gate is a useful result, not permission to change scope. Stop before billing, cloud upload, pruning or swapping models.
