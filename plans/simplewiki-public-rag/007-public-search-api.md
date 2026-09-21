# 007 — Public search API with bounded database access

Status: TODO. Dependencies: 001,002,006. Suggested executor: Terra; owner reviews access boundary.
Read handbook, ARCHITECTURE.md, CONTRACTS.md API section and SOURCES.md. Inspect actual locked Wrangler/TS APIs.

## Outcome and ownership

Own apps/worker/src/, apps/worker/wrangler.jsonc, apps/worker/tests/, packages/contracts fixtures as needed, docs/api.md. Coordinate root script/lock changes.
Anonymous users can read shared corpus results. No public database key, raw query passthrough, hosted embedding inference or LLM proxy.

## Steps

1. Implement createApp(env, dependencies) for test injection; production export wraps it. Separate request validation, rate limiting, Qdrant transport and output mapping. Use native fetch; avoid a heavy server SDK in Worker.
2. GET /api/config returns pinned browser model contract and active corpus. Separate nonsecret deployment variables from secrets. Config must be validated at startup/request initialization; missing key/collection/contract => explicit unavailable response.
3. Add POST /api/search exactly as CONTRACTS.md. Implement streaming byte limit before JSON parse, including chunked requests. Validate schema plus finite 384-vector, approximate unit norm and matching IDs. Normalize within accepted norm range only.
4. Reject collection names, filters, endpoints and arbitrary Qdrant parameters supplied by callers. Construct one fixed /collections/<configured-collection>/points/query request, top 24, selected payload and with_vector=false.
5. Limit upstream request duration to 5 seconds with AbortController. Cap upstream response at 256 KiB. Parse documented response envelope using installed server contract. Validate each hit and choose max 2/page, up to requested limit. One invalid upstream payload should produce a controlled upstream error rather than unsafe HTML.
6. Add separate bindings for SEARCH_RATE_LIMITER and CONFIG_RATE_LIMITER. Search default 20/minute per Cloudflare trusted IP; config 120/minute. Local tests inject deterministic limiters. Missing production limiter fails closed; do not use process-memory counters as a production replacement. Shared-IP visitors can collide; document and measure.
7. Add SEARCH_ENABLED kill switch. Return sanitized error codes/statuses and request IDs; log only status, duration and coarse result count. Never log keys, vector body, full query, sources or provider responses. No analytics dependency.
8. Production site is same origin. Reject unexpected Origin when present; permit absent Origin for command-line public clients. This is browser policy, not bot authentication. Do not trust caller-controlled X-Forwarded-For as the limiter key. Development allows explicit localhost origin only.
9. Add accurate method/unknown-route handling. /api/* must never fall through to index.html. OPTIONS may explain allowed methods without contacting Qdrant. Browser retries only by user action except one config refresh after 409.
10. No cache for this release. Caching vectors requires exact request/model/corpus identity and can wait for load evidence.
11. Build Worker static-assets routing for later frontend build: API routes run Worker first, static assets served normally. Pin compatibility_date to tested date. Test deploy --dry-run packaging with no account secret.
12. Add HTTP contract fixtures and transport mock asserting target URL, headers and payload shape; redact secret in failure messages.

## Verification gates

- npm run test --workspace apps/worker
- npm run typecheck
- npm run lint
- npm run build
- npm exec --workspace apps/worker -- wrangler deploy --dry-run

Required cases: success; 400 extra fields/wrong vector; 409 old corpus/contract; 413 without Content-Length; 415 wrong media type; 429 with Retry-After; 503 missing limiter/key/kill switch; 504 timeout; 502 malformed/oversized upstream; API 404/405; no upstream call after early rejection; payload projection prevents vector exposure.
Then local Worker -> local Qdrant smoke test using scoped/local test credential configuration, never actual cloud credentials in fixtures.

## Completion and STOP

Report mocked transport and real local results separately. Workers free CPU compatibility remains a live gate in 011; don't infer it solely from unit tests.
STOP on unavailable rate-limit binding, incompatible cloud APIs or >10 ms measured free-tier CPU in deployment. Hand back before replacing hosting architecture or adding billing.

