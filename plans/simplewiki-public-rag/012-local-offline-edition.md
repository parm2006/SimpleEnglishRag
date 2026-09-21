# 012 — Local search, article reader and Ollama answers

Status: TODO. Dependencies: 004..006,008,010; reuse 009 answer schema/prompt. Follows public release by default.
Suggested executor: Terra.
Read handbook, ARCHITECTURE.md, CONTRACTS.md local sections and SOURCES.md.

## Outcome and ownership

Own src/simplewiki/{local_app,answers}.py, local CLI, stores adapter reuse, apps/web local feature handling, scripts/bundle.py, docs/{offline,restore}.md, tests/integration/test_local_app.py, tests/e2e/local.spec.ts.
A prepared computer can restart and search with external networking disabled. Public-site search never depends on this local server.

## Steps

1. Add FastAPI/uvicorn as optional local dependency group; exact versions locked. serve --build <directory> --host 127.0.0.1 --port 8000 validates ready manifest and local model cache before startup.
2. Serve built frontend from local app. Implement same config/search responses; features identify local article and answer support. Add /api/search-text so Python handles query embedding without browser model download. Frontend chooses it only when local config advertises it.
3. Reuse SearchStore and model wrapper. Qdrant endpoint is configured loopback by default; do not expose database/HTTP app on all interfaces. User explicitly configures remote access later if desired.
4. Add article reader endpoint with safe page ID parsing and parameterized SQLite query. Render title/full sections/source attribution. SQLite FTS5 title/text search provides basic browsing if vector service is unavailable; add /api/browse?q= with capped query length/results and literal-safe search syntax.
5. Every vector/corpus/model contract must match local manifest. Model loading must use local files only in offline mode; no hidden download on import.
6. Add local /api/answer. Accept query + chunk IDs; retrieve authoritative chunks from SQLite for current corpus. Build same context/source ID mapping and structured output validation as public generation.
7. Call Ollama only at configured loopback endpoint /api/chat with stream=false initially, bounded timeout and chosen installed model. No arbitrary URL from request. List available models via local setup command or owner config; don't assume a specific model fits RAM/GPU.
8. Provider response follows same answer schema. Missing model/service -> readable error with working sources. Concurrency default one local generation at a time to avoid exhausting machine memory; cancellation disconnects call best-effort and discards late output.
9. Prepare bundle manifest with app version, Python/npm locks, built frontend, corpus SQLite, vectors/shards or verified Qdrant snapshot, pinned embedding weights/tokenizer, Qdrant image version/digest and licenses. Ollama model distribution is optional and subject to its own license/size; record required model and how it was prepared.
10. Offline setup must prepare runtime dependencies before disconnect: uv environment or OS-specific wheel cache, Docker image saved/available, model cache, frontend WASM if browser path supported. Build separate Windows/Linux instructions; don't call one platform's Python environment portable to another.
11. bundle command writes into a new explicit output directory, computes per-file SHA-256 and disk requirement, excludes secrets/caches unrelated to selected model. No automatic upload. Include README with exact start/stop/restore commands and snapshot compatibility limitations.
12. Test from fresh local data directory: restore corpus/index, launch app, disable external networking, restart process, search five questions, open full article, generate one answer with prepared Ollama model. Browser network log must show no external requests. If vector service fails, browse still works.
13. Document Kiwix as an optional separately downloaded reader, not an implemented fallback unless actually bundled/tested. Avoid claiming machine-independent offline functionality from one warm-cache test.

## Verification gates

- uv run pytest tests/integration/test_local_app.py
- npm run test:e2e
- uv run simplewiki serve --build data/builds/full --host 127.0.0.1 --port 8000
- uv run simplewiki bundle --build data/builds/full --output data/releases/offline-test
- Offline restart + search + article + Ollama test with recorded machine/model and network disabled.

Tests include unknown chunk ID; wrong corpus; oversized body; SQLite injection string; missing model; unavailable Qdrant; path traversal attempt; canceled generation; invalid citations; remote Origin rejected.

## Completion and STOP

Record measured disk/RAM needs, supported OS, installed generation model and offline evidence. If no local model available, search/reader can finish but generation remains unverified and this plan is not fully DONE.
STOP on hidden network access or incompatible snapshot; use portable artifacts to rebuild where supported, not fabricated offline claims.

