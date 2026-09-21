# 003 — Download and clean the complete article snapshot

Status: TODO. Dependencies: 001 and 002 (frozen configuration). Suggested executor: Terra.
Read handbook baseline/drift rules, ARCHITECTURE.md and CONTRACTS.md. No existing parser exemplar predates 001.

## Outcome and ownership

Own src/simplewiki/{download,extract,clean}.py, related CLI commands, tests/unit/test_{download,extract,clean}.py, tests/fixtures/wiki/, docs/corpus-policy.md.
Produce a verified source dump and streaming article records with accounting. Do not chunk or embed yet.

## Steps

1. Implement download --snapshot YYYYMMDD --output-dir data/raw. Resolve the regular pages-articles.xml.bz2 for that completed dated snapshot plus publisher checksum file. Prefer regular XML for sequential reading; do not download history. Confirm HTTP status/content and completed dump listing.
2. If dated URLs are unavailable, resolve the current published latest dump once, record resolved URL/headers/listed date and checksum before use. Abort if the checksum listing changes during download. Never use an unrecorded mutable latest source in a manifest.
3. Download to .part, stream to disk, validate publisher checksum and compute local SHA-256. Rename only when verified. Retry transient network errors with capped exponential backoff and jitter: 1,2,4,8,16 seconds, at most five retries; honor reasonable Retry-After. Resume only when Range support and unchanged validator are confirmed; otherwise restart the partial file explicitly. A wrong checksum is a failed artifact, not a success.
4. Build tiny synthetic MediaWiki XML fixtures with namespace declarations and actual current dump schema: normal article, redirect element, redirect markup, template page, list, stub, empty page, disambiguation, Unicode title, large section, nested templates and a malformed/truncated file.
5. Stream bz2 through mwxml; process current revision per page, not a parent revision ID by mistake. Use a real dump schema smoke test because XML layouts evolve. Keep memory bounded to one page and bounded output batch. Preserve namespace and page/revision IDs in dispositions.
6. Emit main-namespace article records. Store redirects as aliases but do not embed them as duplicate articles. Keep disambiguation pages flagged and keep stubs/lists; do not filter them away based on length.
7. Build cleaner over markup AST. Preserve section hierarchy, paragraph boundaries, list items, link labels, HTML entities and useful captions. Strip ref bodies, comments, scripts/styles, navigation/maintenance templates and category markup from readable prose.
8. Template policy must be explicit: support common text wrappers and human-readable infobox parameter values with labels; do not execute templates, fetch missing definitions or stringify raw template syntax. Unknown templates generate counts and sampled examples; original dump remains available. A generic AST strip_code call does not expand Wikipedia templates.
9. Tables: retain readable cell text row by row with header labels when available; never invent associations. Preserve unhandled tables in source and count them in audit. Keep visible attribution/licensing notices separately even if excluded from embeddings. Do not strip every footer blindly.
10. Normalize Unicode NFC, newline format and excessive blank lines. Do not remove accents or lowercase everything. Preserve full cleaned text even when a future embedding prefix is shortened.
11. Stream extracted article/disposition JSONL into immutable output shards with checkpoint metadata. Resume by replaying compressed input and skipping fully committed page batches; no arbitrary seek into a bzip2 stream. Commit shard then checkpoint atomically; repeated replay must not duplicate committed records.
12. Add audit reporting: all page totals by namespace/disposition, top unknown templates, representative raw/clean pairs and error page IDs. A parse error must exit nonzero or leave manifest incomplete. A release requires zero unexplained article errors; known non-text/empty cases require reasons.
13. Manually review 50 diverse real articles (science/history/geography/biography/list/short/long/template-heavy). Check titles, sections, numbers and lost text. Update narrow cleaner rules with fixtures before processing full data.

## Verification gates

- uv run pytest tests/unit/test_download.py tests/unit/test_extract.py tests/unit/test_clean.py
- uv run simplewiki download --help
- uv run simplewiki extract --input tests/fixtures/wiki/small.xml --output data/test-extract
- uv run simplewiki extract --input tests/fixtures/wiki/small.xml --output data/test-extract --resume
- uv run ruff check .
- uv run mypy src/simplewiki

Expected: second run produces identical committed artifacts; every source page has one disposition; redirects/non-main excluded from embedding candidates; truncated XML does not mark completion. Test interrupted transfer, server ignoring Range, checksum mismatch and output directory already containing a different source.

## Completion and STOP

Write report with source URL/date/checksum and reviewed examples. Full download is appropriate once CLI fixtures pass; full extraction waits for chunk/corpus integration if desired.
STOP if real schema is unsupported or cleaner destroys essential prose. Handback exact page examples; never report "all Wikipedia ingested" from a sample.

