# 008 — Public browser search and readable sources

Status: DROPPED. Dependencies: None.
Decision: Public browser frontend permanently dropped per user instruction. `ser` operates purely as a local CLI (`ser`), interactive terminal REPL, Python library, and MCP server.
Read handbook, ARCHITECTURE.md and CONTRACTS.md.

## Outcome and ownership

Own apps/web/src/, apps/web/index.html, apps/web/public/ notices and small assets, apps/web/tests/, tests/e2e/search.spec.ts, Playwright configuration.
Visitors can search without account/key; no generation yet. Do not add database settings to the normal UI.

## Steps

1. Build simple responsive layout: project title, plain description, snapshot date, labeled query box, Search button, progress/status region, result cards and source/licensing footer. Use real accessible HTML, visible focus and 320px mobile layout.
2. Implement API client with typed validated responses and AbortController. Load /api/config on startup. Render explicit unavailable state if malformed or unreachable; don't substitute demo results.
3. Use dedicated Web Worker for model initialization/tokenization/inference; UI thread never runs transformer inference. Worker messages include request_id and kind: init/progress/ready/embed/result/error. Coalesce initialization into one promise; prevent duplicate model allocations.
4. Model loads lazily after first Search, caches through supported browser storage, pinned revision/dtype. Model files come from approved Hugging Face artifacts; static deployment must not bundle an oversized ONNX file. WASM runtime assets can be self-hosted when under platform limits. Verify exact CDN redirects and CORS; do not proxy arbitrary URLs.
5. Show initial model download and preparation progress, with actual percentage only when bytes are known. Explain first-use download before/while it starts. Give retry after network failure and a way to clear the model cache. No repeated automatic download loops.
6. State transitions: idle -> loading_model -> embedding -> searching -> results/empty/error. Starting a new search increments generation ID, aborts old fetch and ignores old worker messages. Cancel returns to usable state; if inference cannot abort, ignore its output instead of calling it canceled while later displaying it.
7. Enforce character/token limits with meaningful errors, submit on Enter, keep current query editable. Disable duplicate submit for same in-flight query; clear old answer state on any new search.
8. Render full returned chunks, title/section, source link and pinned revision link. Generate links from validated fixed origin or validated returned URLs. Never dangerouslySetInnerHTML. React-escape source text; test malicious markup in title/text.
9. Show result scores only in optional developer diagnostics, never as "confidence 92%". Empty results show "No passages found"; weak-looking results remain passages, not a confirmed answer.
10. Handle 409 by reloading config once, invalidating incompatible model state and prompting retry. Handle 429 cooldown from Retry-After; bounded parse if header invalid. On database outage, retain previous results labeled as from previous search and offer retry, or clear with explicit state; don't associate them with new query.
11. Persist no query, key or vector to storage by default. Optional URL query sharing is deferred. Model cache is the only intended persistent browser data.
12. Set production CSP from observed model/WASM requirements. Avoid wildcard connect-src and third-party scripts. Allow fixed Gemini origin only when 009 lands. Test CSP with actual browser model; WASM permissions and worker-src must match locked runtime.
13. Add Playwright tests with injected tiny embedder and mocked API for fast deterministic flow, then a separate real-model/local-Worker/local-Qdrant smoke. Test desktop Chromium, Firefox and WebKit; report unsupported runtimes explicitly. Do not claim mobile tested from viewport resizing alone.

## Verification gates

- npm run test --workspace apps/web
- npm run typecheck
- npm run lint
- npm run build
- npm run test:e2e
- npm run test:embedding -- --offline

E2E: keyboard submit; model progress; success; empty; cancel; query A slower than B (only B displays); cache download failure/retry; 409 refresh; 429; source text XSS fixture; full source links; screen-reader status; no key/account required.
Real browser smoke: ask five real questions and confirm returned page IDs against CLI on same corpus.

## Completion and STOP

Report tested browser versions, cold/warm model timing, download bytes and any unsupported browser. Capture screenshots for owner review without claiming simulated results are live.
STOP if model cannot load under CSP/CORS, browser runtime disagrees with parity, or UI would need a different embedding model. Handback rather than replacing inference silently.

