# 009 — Optional answers with a visitor's Gemini key

Status: TODO. Dependencies: 006,008. Suggested executor: Terra; Luna may build Settings panel against frozen interface.
Read handbook, ARCHITECTURE.md, CONTRACTS.md answer section and current provider docs.

## Outcome and ownership

Own apps/web/src/generation/{context,prompt,schema,gemini,controller}.ts, answer/settings components, tests/e2e/answers.spec.ts, tests/fixtures/answers/, docs/answer-evaluation.md.
Search remains useful without a key. Scope is one provider initially; no owner-funded API and no chat memory.

## Steps

1. Define generation adapter accepting query + validated selected sources + AbortSignal and returning structured AnswerResult. Keep provider transport separate from context selection and citation validation.
2. Select <=6 sources from current results, respecting 24,000-character budget by including whole chunks only. Map to S1..S6 for this request. Freeze source mapping while response is in flight; never relabel against later search results.
3. Build prompt from fixed instructions and JSON-serialized source data. Sources are evidence, never instructions. Include no tools, web search or current-date claims outside source snapshot. Require structured schema from CONTRACTS.md.
4. Implement fixed Gemini REST endpoint using current documented generateContent interface (or verified replacement if changed, with handback). Select an actually available model using owner's test account at execution and record model ID in nonsecret config. Do not blindly copy current documentation's sample model name or assume a free tier.
5. Expose Settings with masked key input, clear key button and model setting only if needed. Hold key in tab memory; clear on reload. Explain key goes directly to Google and question/source passages are sent when Generate is clicked. Never ship an owner key or collect it through /api/search.
6. Use x-goog-api-key header, not URL query parameter. Restrict endpoint to Google origin; no arbitrary user endpoint. Redact provider errors. Timeout 45 seconds, cancel control, no auto-retry or generation triggered by typing.
7. Confirm real browser CORS and supported model generation with the owner's supplied key using normal input. No keys in Playwright traces/screenshots/fixtures. Automated tests use fake key and mocked Google transport.
8. Validate response schema and all source IDs before display. Unknown ID, no citation on answered sentence, invalid JSON, blocked/empty/truncated response -> generation error with intact sources. Render text plus app-built citation links. No arbitrary model HTML, images or URLs.
9. insufficient_evidence -> fixed readable message. Valid citation IDs are necessary but don't prove support; add a brief generated-answer label and easy source inspection.
10. Integrate latest-request-wins: changing question, starting search, changing corpus or canceling invalidates answer. Stale result never overwrites current UI. Clear key cancels generation and removes sensitive state.
11. Test 20 answerable and 10 unanswerable questions with real passages. Human checks every factual sentence against citations. Gate: >=90% supported factual sentences, >=90% correct abstention on unanswerable set, zero invented citation IDs. Report sample size and model ID; do not market this as broad 90% accuracy.
12. If live validation can't run because no key/account is available, ship search with generation feature flag off and mark this plan BLOCKED for live validation; don't pretend mocked provider calls prove compatibility.

## Verification gates

- npm run test --workspace apps/web
- npm run test:e2e
- npm run typecheck
- npm run build
- Human evaluation report on pinned corpus/model.

Tests: known/unknown source IDs; missing citations; HTML in model text; timeout; 401; 429; blocked response; invalid/truncated JSON; budget cap; cancel; stale answer; clear key; network spy asserts no key reaches Worker, storage or logs.

## Completion and STOP

Report mocked tests and separately live provider/CORS/citation evaluation. Keep secrets out of reports.
STOP if provider now requires backend credential handling or unsupported API changes. Owner can release sources-only while the provider adapter is resolved; no automatic paid proxy.

