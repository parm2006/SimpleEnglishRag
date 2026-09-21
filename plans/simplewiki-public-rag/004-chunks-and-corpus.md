# 004 — Section-aware chunks and canonical SQLite corpus

Status: COMPLETED (Vector-Native Storage). Dependencies: 002, 003.
Completed: Boundary-aware chunking engine implemented in `src/ser/chunk.py` (1,200 char window, 200 overlap, stub filtering). Canonical SQLite storage was superseded by storing article metadata and prose directly in Qdrant Cloud point payloads with `on_disk=True` per architectural mandate.
Read handbook, ARCHITECTURE.md and CONTRACTS.md.

## Outcome and ownership

Own src/simplewiki/{chunk,corpus,manifest}.py, config/pipeline.json, chunk CLI, tests/unit/test_{chunk,corpus,manifest}.py, tests/fixtures/chunks/, scripts/select-sample.py.
Generate all chunks before calculating embedding cost. Preserve complete cleaned articles for local browsing.

## Steps

1. Create SQLite schema from CONTRACTS.md with schema version, transactional batches, foreign keys and indexes on article title/page lookup and chunks by page. Do not use Qdrant as the only content archive.
2. Implement pure chunk_article(article, tokenizer, config) -> iterator[Chunk]. Keep heading paths; Introduction handles lead text. Pack paragraphs within one section toward 320 body tokens; enforce 480 total tokenizer tokens after formatting.
3. Split an oversized paragraph by sentence boundaries, then character spans selected by tokenizer counts if a sentence is still too long. Preserve source substring order; do not round-trip token IDs into corrupted text. For long section continuation, overlap at most 40 body tokens; ensure each iteration advances.
4. Never merge different articles. Merge small adjacent paragraphs only within the same section. Keep one-sentence stubs. All nonempty indexed article bodies must contribute a chunk. A tiny section is allowed rather than silently discarded.
5. Apply prefix overhead shortening rule, record it and retain full title/heading for display. Test huge titles/heading paths, giant single words, URLs, tables, lists, empty sections and emoji. Reject unexplained truncation.
6. Compute corpus/chunk IDs deterministically. Save section_index to disambiguate repeated section headings. Preserve order. Generate SQLite rows plus <=5,000-row JSONL chunks shards. Use chunk text hash to detect accidental changes.
7. Make SQLite the authoritative checkpoint transaction: insert articles/sections/chunks/dispositions and committed progress in one transaction. Export deterministic JSONL from committed rows. Crash between SQLite commit and export can safely re-export; don't maintain two irreconcilable progress counters.
8. Finish manifests only after verifying shard row counts, checksums, uniqueness and total page accounting. Duplicate chunk IDs with different text is fatal. Actual content input/config changes require a new corpus ID.
9. Implement deterministic sample selection: score page IDs with a fixed hash seed, select 10,000 eligible articles across the entire stream rather than first alphabetical pages. Keep a smaller 1,000-article sample for first retrieval. Record selected page IDs and selection fingerprint.
10. Avoid reading all full articles into memory when sampling; bounded heaps of IDs or SQLite queries are fine. Include additional stress cases separately so long-article tests do not bias sizing extrapolation.
11. Add verify --build command to check SQLite integrity, foreign keys, manifests, ID uniqueness, token limits and article disposition reconciliation. Use full scan when preparing release and optional sample mode for development.

## Verification gates

- uv run pytest tests/unit/test_chunk.py tests/unit/test_corpus.py tests/unit/test_manifest.py
- uv run simplewiki chunk --extracted data/test-extract --build data/builds/fixture
- uv run simplewiki verify --build data/builds/fixture
- Repeat build with same inputs in another test directory and compare content/shard hashes (timestamps may differ only outside content identity).
- uv run ruff check .
- uv run mypy src/simplewiki

Tests must reconstruct covered source spans modulo documented whitespace and overlap, assert <=480 formatted tokens, ensure all nonempty articles contribute, and interrupt/resume around transaction/export boundaries.

## Completion and STOP

Report articles/chunks/token distribution, prefix-shortening count, biggest articles and rejected cases. No full model run.
STOP on unexplained content loss, ID collision, incompatible schema or different bytes after equivalent rebuild. Use handback protocol.

