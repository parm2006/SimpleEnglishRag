# 005 — Resumable local embedding jobs

Status: TODO. Dependencies: 002,004. Suggested executor: Terra.
Read handbook, ARCHITECTURE.md and CONTRACTS.md. Inspect model wrapper from 002 and manifest/shard writer from 004.

## Outcome and ownership

Own batch orchestration in src/simplewiki/embed.py, embed CLI, tests/unit/test_embedding_job.py, tests/integration/test_model_shards.py, docs/ingestion.md.
Produce portable vectors once; Qdrant and Postgres will consume the same artifacts.

## Steps

1. Require verified chunks manifest and exact embedding contract before loading model. Fail on missing revisions, token overflow, non-ready extraction/chunk stage or mismatched hash. Keep stage-specific completion: chunk-ready is sufficient here; overall build-ready occurs after vectors/index verification.
2. For each JSONL shard, stream records in stored order into bounded batches, default batch 32 on CPU. User may choose --device cpu/cuda and --batch-size; record hardware. No automatic dependency/GPU driver installation.
3. Encode embedding_text without query instruction. Store float32 arrays (N,384), finite and normalized. Persist IDs alongside or rely on hashed source shard order plus explicit row-count contract; never join by unreliable batching order.
4. Write .npy temporary shard, flush/close, hash, rename atomically, then mark completed in stage manifest. Re-running verifies completed shard checksum and skips it. A temp file is never considered committed.
5. Handle process interruption and OOM. Reduce batch size on recognized OOM a bounded number of times, log safe metadata; do not skip examples. Fatal failures leave recoverable progress and nonzero exit.
6. Add throughput progress: done/total chunks, chunks/sec, estimated remaining time, completed shard count. Report estimates from measured batches rather than guessed hours.
7. CLI: embed --build <directory> --device cpu --batch-size 32 [--resume]. --resume refuses changed chunks/config/model. --dry-run prints counts, raw vector bytes and expected output paths without inference.
8. Run first on fixture, then 1,000-article sample. Confirm top/bottom shard IDs and rows align. Cache model weights and support --offline-model so local reruns do not access network.
9. Add corruption tests: missing row, reordered source shard, altered byte, wrong vector shape, NaN, truncated .npy, crash after rename before manifest update. Recovery validates orphan final file before accepting it; otherwise recomputes safely.

## Verification gates

- uv run pytest tests/unit/test_embedding_job.py
- uv run simplewiki embed --build data/builds/fixture --dry-run
- uv run simplewiki embed --build data/builds/fixture --device cpu --batch-size 8
- uv run simplewiki embed --build data/builds/fixture --resume
- uv run simplewiki verify --build data/builds/fixture
- uv run pytest tests/integration/test_model_shards.py -m model

Expected: unchanged committed vectors on resume, no ID/order mismatch, invalid contract rejected before expensive inference. Ordinary unit tests use deterministic fake embedder; report real-model tests separately.

## Completion and STOP

Record actual throughput, model cache bytes, output bytes and stage counts. Full-corpus embedding is authorized by plan 010 only after sizing gates.
STOP on parity regression, corrupt source identity or unjustified model changes. Do not re-embed with a different model under the same corpus ID.

