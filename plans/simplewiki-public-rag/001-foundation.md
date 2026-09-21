# 001 — Repository, tooling and executable contracts

Status: TODO. Dependencies: none. Suggested executor: Terra; routine fixtures may use Luna.
Planned-at baseline: 2026-09-15, no Git repository or code. Read EXECUTOR-HANDBOOK.md for baseline hash and drift rules, plus ARCHITECTURE.md and CONTRACTS.md.

## Outcome and ownership

Create a reproducible skeleton with real validation commands. Own root build/config files, schemas/, packages/contracts/, empty app/package entry points, src/simplewiki/{__init__,cli,config,models}.py, tests/unit/test_contracts.py, tests/fixtures/contracts/, scripts/check-contracts.mjs, .github/workflows/ci.yml, docs/development.md.
No corpus download, model inference or cloud provisioning.

## Steps

1. Inspect all files and preserve the historical roadmap. Check git, uv, Python, Node/npm and Docker availability without installing globally. Document missing prerequisites and official installation steps for the owner. Target Python 3.12 and a supported Node LTS satisfying selected Vite/Wrangler engines; record the actual Node version. Run Docker Desktop in Linux-container mode for later Qdrant.
2. Initialize Git if absent when executing this plan. Add .gitignore before any data: data/, models/, .venv/, node_modules/, dist/, coverage/, test-results/, playwright-report/, .env*, .dev.vars*, *.snapshot. Explicitly allow sanitized .env.example and .dev.vars.example. Keep lockfiles and small fixtures tracked. No git add . before reviewing untracked files.
3. Create uv Python package using src layout and a simple argparse or Typer CLI entry point named simplewiki. doctor reports Python/tool versions and writable data path, with no credentials. Add --help. Configure ruff, mypy, pytest and markers qdrant/model/live. Default unit tests exclude network/model work.
4. Create npm workspaces apps/web, apps/worker, packages/contracts, packages/embedding. Use TypeScript strict mode. Select compatible React/Vite, Wrangler, Vitest, ESLint, Playwright, @huggingface/transformers; avoid choosing every latest package independently if their peer versions conflict. Freeze resolved versions in package-lock.json and uv.lock; document engines.
5. Implement JSON Schemas for config, search request, search response, error, article/chunk, manifest and structured answer from CONTRACTS.md. Use draft 2020-12 consistently; additionalProperties=false where specified. Runtime TS validation may use Ajv; Python uses jsonschema or explicit typed validators. Do not maintain subtly different handwritten schemas.
6. Add valid/invalid JSON fixtures shared by Python and TS: wrong vector length; unknown field; string numeric value; mismatched enum; negative limit; malformed IDs; absent license; empty answer; bad citation shape. Numeric finite/norm and cross-field checks require semantic validators beyond JSON Schema.
7. Create real lint/typecheck/test/build scripts with meaningful behavior, no echo-success scripts or --passWithNoTests. Root scripts orchestrate workspaces in dependency order using a portable Node runner when needed. Build contracts before dependent apps. Implement minimal tested config and placeholder UI that clearly says corpus not loaded; no fake search results in production paths.
8. Establish exemplars: tests/unit/test_contracts.py for pytest, packages/contracts/src/search.test.ts for TS, apps/web/src/App.test.tsx for DOM tests. Subsequent plans should copy conventions, not their test content.
9. Create compose.yaml with an explicit, tested Qdrant version (never latest), Linux image, persistent named volume and port 127.0.0.1:6333:6333. Choose version compatible with intended cloud at deployment; record image digest. No production exposure or credentials in tracked files.
10. Set CI to run frozen dependency installation, unit/schema checks, lint, typecheck and builds. Browser/model/Qdrant integration jobs are introduced by their plans. Pin action versions/revisions according to owner's repository conventions once available. No deploy or secrets on pull-request CI.
11. Establish dev:web and dev:worker scripts per RUNBOOK.md: loopback ports 5173 and 8787, explicit Vite /api proxy, separate local test configuration. test:e2e is introduced with actual browser tests in 008 and test:embedding in 002; don't create fake success placeholders for future scripts.

## Verification gates

Run from repository root:
- uv sync --locked
- uv run simplewiki --help
- uv run simplewiki doctor
- uv run ruff check .
- uv run ruff format --check .
- uv run mypy src/simplewiki
- uv run pytest tests/unit
- npm ci
- npm run lint
- npm run typecheck
- npm test
- npm run build
- docker compose config

Expected: each exits zero; one deliberate invalid shared fixture fails validation in both languages. Remove the deliberate failure after confirming the assertion. Build output contains no environment secret. Current plans do not claim any of these commands work before this step.

## Completion and STOP

Write reports/plan-001.md with actual versions, scripts, file exemplars and initial revision if committed. Update index row.
STOP on unresolvable dependency/engine conflicts or changed contract requirements; write handback-001-tooling.md using handbook. Do not invent success commands or install paid tooling.
