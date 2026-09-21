# 011 — Deploy the shared public corpus and site

Status: TODO. Dependencies: 007,008,010 GO; 009 if generated answers enabled; 013 instead if Postgres selected.
Suggested executor: Terra for config/tests; owner for account credentials and public release.
Read handbook, ARCHITECTURE.md, CONTRACTS.md and provider docs linked in SOURCES.md.

## Outcome and ownership

Own deployment config/scripts, docs/{deployment,operations,release-checklist}.md, reports/release.md, CI checks and sanitized examples.
A public URL works from a second device with no Qdrant account, key or local server.

## Step A — Account and preflight checklist

1. Owner signs into Qdrant Cloud and Cloudflare. Confirm actual free resources, region, API permissions and Worker bindings; record plan names/limits. Do not activate billing automatically.
2. Create a Qdrant free cluster in a suitable region. Confirm server version matches supported client/query APIs. Free availability/inactivity policies must be read at release time.
3. Create operator ingestion credential privately. For first collection creation, management access may be required; keep it separate from later read key. Store locally in ignored environment/credential mechanism, never command-line literals or reports.
4. Create new physical corpus collection. On a free cluster, use batch upload from portable artifacts as default so an extra uploaded snapshot does not double disk unexpectedly. Respect peak headroom.
5. Upload resumably. Wait for indexing/optimizer completion; verify exact point count, ID digest and sampled payload/vector checks. Network failures resume; never restart by wiping the collection.
6. Create a collection-scoped read-only database key for this exact collection with explicit expiry/rotation date. Privately test search succeeds. Verify write denial using a disposable test collection/key if feasible; never test delete against live content. Record permission scope without key value.
7. Store QDRANT_API_KEY via wrangler secret put; nonsecret variables include QDRANT_URL, QDRANT_COLLECTION, CORPUS_ID, EMBEDDING_CONTRACT_ID, SEARCH_ENABLED and snapshot date. Do not prefix secrets VITE_. Secret prompts are interactive and not pasted into agent transcripts.

## Step B — Single-origin deployment

8. Configure Worker static assets directory as apps/web/dist via correct relative path from Wrangler config. API routes run before asset fallback. Use workers.dev URL initially; a custom domain is optional.
9. Model ONNX files load from pinned hosted model artifacts; don't include >25 MiB model in Worker static assets. Confirm no data/, corpus DB or vector shards in frontend bundle.
10. Run unit/contract/E2E/build checks and Worker dry-run. Review production bundle and sourcemaps for accidental environment data. Secret scanning uses safe patterns/sentinels, not printing secret values.
11. Deploy with npm exec --workspace apps/worker -- wrangler deploy after the owner has authorized public release. Keep deploy manual initially; CI checks are automatic. Record build commit and deployment version.
12. Configure rate binding namespace IDs and environment-specific vars explicitly in each deployment environment; verify Wrangler environment inheritance rather than assuming secrets/bindings copy across.
13. API config contains full browser contract and correct corpus. Missing/stale config must prevent search, not search incompatible vectors. Unknown /api path returns JSON 404, not HTML.

## Step C — Live release acceptance

14. On a clean browser/profile and second device, open public URL. Submit 10 curated questions without any keys. Compare article IDs with local full-corpus baseline. Inspect source text and revision links.
15. Inspect network: browser calls site/model host, not Qdrant directly. Site responses reveal no Qdrant key/vectors. Download/model/CSP works on actual deployment.
16. Exercise 400,409,413,429 and temporary SEARCH_ENABLED=false. Ensure limits reject before upstream. Do not run abusive high-volume load against free service; use bounded 100-request, 1/5-concurrency test after permission for own cluster.
17. Inspect actual Worker CPU and Qdrant resource metrics. Free Worker CPU must fit current limit; hitting it is a release blocker, not solved by wishful caching. Confirm p95/error targets and no model inference inside Worker.
18. Enable Gemini only if 009 live gate passed. Otherwise feature flag off and release explicitly search-only. Optional failure must not block ordinary source search.
19. Record live URL, corpus/date/counts, model contract, server version, Worker version, tested browsers, known limits, tested recovery method and key expiry date.

## Step D — Operations and updates

20. Keep source dump, SQLite, shards, vectors, model lock and build manifests on a separate disk/storage location. Backups must be restorable independently of cloud inactivity. Snapshot only when quota has room; never assume a full snapshot fits beside a full collection.
21. Document manual restore: new compatible collection -> portable batch import -> verify -> new scoped read key -> Worker config update -> smoke tests. Practice with small fixture before relying on full backup.
22. Corpus updates are manual v1. Build next snapshot locally first. If two full collections do not fit together, choose documented maintenance outage or larger capacity with owner. Do not delete current corpus before backup/restore verification and explicit release decision.
23. When space allows two collections: import/verify new -> deploy matching corpus config + collection + key as one version -> old browser gets 409 -> check -> retain old until rollback window ends.
24. Rollback Worker code alone is insufficient when data/key/model differ. Record complete release tuple and restore it together. Key rotation must retain valid old access until new deployment succeeds, then revoke old key.
25. Inactivity: explain potential suspension/deletion and recovery steps. No synthetic keep-alive automation or paid upgrade is silently introduced.
26. Monitoring runbook: manual weekly resource/key-expiry check and error review; if owner requests automation later, save a real monitor. On overload, use kill switch/429, inspect demand, then discuss capacity.

## Verification gates

- All 001 common code checks.
- npm run test:e2e
- npm exec --workspace apps/worker -- wrangler deploy --dry-run
- uv run simplewiki verify --build data/builds/full
- Recorded live acceptance Steps 14..19.
- Small-fixture restore rehearsal passes, and full release artifacts have verified hashes.

## Completion and STOP

Write actual URL and evidence; don't mark DONE from deployment command alone.
STOP for missing accounts/secrets, failed capacity/CPU/CORS, unexpected billing or absent release authorization. Complete safe config/testing while blocked; report exact owner action. No paid purchase or deletion of current collection by inference.

