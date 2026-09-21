# Operator runbook and milestone gates

These commands are the interface that the numbered plans must implement. They do not exist in the current repository. Run commands only after the implementing plan is complete. All examples use PowerShell from the project root. Replace example input paths with the verified paths printed by the downloader; never paste keys into these commands.

## 1. Prepare the development environment — 001

Install Git, uv, Python 3.12, a supported Node LTS, and Docker Desktop with Linux containers if absent. Use official installers and verify versions. Accounts are needed only for public deployment and optional live Gemini testing.

```powershell
Set-Location 'C:\Users\parth\Projects\SimpleEnglishRAG'
git --version
uv --version
node --version
npm --version
docker version
uv sync --locked
npm ci
uv run simplewiki doctor
```

Do not run frozen installs before 001 creates lockfiles. Required npm dev scripts: dev:web on 127.0.0.1:5173, dev:worker on 127.0.0.1:8787. Vite proxies /api to local Worker during development. Production serves both on one origin. API development uses ignored apps/worker/.dev.vars; production uses Worker secrets.

## 2. Pass the embedding probe — 002

```powershell
npm run test:embedding -- --prepare
npm run test:embedding -- --offline
```

Gate: pinned revisions, matching tokenization/CLS pooling, acceptable numerical/retrieval agreement and a real browser run. Do not proceed to full inference without this report.

## 3. Fixture ingestion — 003..006

```powershell
uv run simplewiki extract --input tests/fixtures/wiki/small.xml --output data/test-extract
uv run simplewiki chunk --extracted data/test-extract --build data/builds/fixture
uv run simplewiki embed --build data/builds/fixture --device cpu --batch-size 8
docker compose up -d qdrant
uv run simplewiki index --build data/builds/fixture --url http://127.0.0.1:6333
uv run simplewiki verify --build data/builds/fixture
```

Gate: rerunning with --resume leaves committed artifacts unchanged and doesn't duplicate points. Run the corrupt/truncated/interrupted fixtures from the plans. The fixture corpus must be clearly identified as a fixture.

## 4. Download and extract a full snapshot — 003/004

```powershell
uv run simplewiki download --snapshot 20260901 --output-dir data/raw
```

The date is an example aligned with planning research. Resolve a completed available dated snapshot at execution. Set the following variable to the actual verified file reported by download:

```powershell
$sourceDump = 'data/raw/simplewiki-20260901-pages-articles.xml.bz2'
uv run simplewiki extract --input $sourceDump --output data/extracted/simplewiki-20260901
uv run simplewiki chunk --extracted data/extracted/simplewiki-20260901 --build data/builds/sample-1000 --sample-size 1000 --sample-seed 42
uv run simplewiki embed --build data/builds/sample-1000 --device cpu --batch-size 32
uv run simplewiki index --build data/builds/sample-1000 --url http://127.0.0.1:6333
uv run simplewiki verify --build data/builds/sample-1000
```

Build evaluation questions from actual sample articles; do not label missing articles as expected hits. Keep fixture/sample/full question files separate under tests/eval/ and use the correct path. Plan 006's questions.jsonl is the baseline for the corpus currently under evaluation, with corpus ID recorded in evaluation metadata. Freeze separate held-out questions for the full release.

## 5. Browser vertical slice — 007/008

Configure local Worker to use sample collection/model contract from build output. Terminal 1:

```powershell
npm run dev:worker
```

Terminal 2:

```powershell
npm run dev:web
```

Open the local frontend URL printed by Vite. Search five questions chosen from the sample. Inspect actual sources. Search must work without a Gemini key. For automated E2E use separate test configuration so local real corpus settings are not overwritten.

## 6. Full-corpus sizing and embedding — 010

```powershell
uv run simplewiki chunk --extracted data/extracted/simplewiki-20260901 --build data/builds/sample-10000 --sample-size 10000 --sample-seed 42
uv run simplewiki embed --build data/builds/sample-10000 --device cpu --batch-size 32
uv run simplewiki index --build data/builds/sample-10000 --url http://127.0.0.1:6333
uv run simplewiki chunk --extracted data/extracted/simplewiki-20260901 --build data/builds/full
uv run simplewiki embed --build data/builds/full --dry-run
uv run simplewiki capacity --build data/builds/sample-10000 --output reports/capacity-sample.json
```

Use actual full chunk count plus measured sample bytes per chunk in the preliminary full projection. Only after it passes local resource preflight:

```powershell
uv run simplewiki embed --build data/builds/full --device cpu --batch-size 32 --resume
uv run simplewiki index --build data/builds/full --url http://127.0.0.1:6333 --resume
uv run simplewiki verify --build data/builds/full
uv run simplewiki capacity --build data/builds/full --output reports/capacity-full.json
uv run simplewiki evaluate --build data/builds/full --questions tests/eval/questions-full.jsonl --output reports/retrieval-full.json
```

Gate: complete article/ID reconciliation, held-out quality, steady/peak capacity and bounded load. Full data must pass before claiming the public site searches all articles. If Qdrant fails, execute 013; sample-only release is a preview explicitly labeled as such.

After recording the extraction audit and passing retrieval gates:

```powershell
uv run simplewiki verify --build data/builds/full --finalize --evaluation reports/retrieval-full.json --audit reports/extraction-audit-full.json
uv run simplewiki verify --build data/builds/full --require-ready
```

## 7. Generation — 009

Supply your own key through the UI, choose verified available model, run live answer evaluation and clear key afterward. No account key is saved in this repository. Search launch can precede answer launch; feature flags must reflect actual tested capability.

## 8. Deploy — 011

Follow 011 in order: provision free cluster, import/verify, scope read credential, set Worker secrets/config, dry-run, deploy, second-device tests. The deployment command is not the entire release. Do not upload a 4 GB corpus beside another 4 GB corpus in a 4 GB cluster.

Provider credentials are owner actions; an executor can prepare config and dry-run packages without them. A future deployment requires the owner's public-release authorization. This planning request does not itself publish anything.

## 9. Offline edition — 012

Prepare the data/model/runtime dependencies online first. Then:

```powershell
uv run simplewiki serve --build data/builds/full --host 127.0.0.1 --port 8000
```

Local API uses /api/search-text so no browser model download is required. Run the full restart test with networking disabled, not just a warm browser tab. Ollama must already have a suitable installed model. Document start/stop commands and disk/RAM from your machine.

## Milestone checklist

| Milestone | Evidence required |
|---|---|
| Tooling ready | Reproducible locks, schemas and passing real scripts |
| Model ready | Cross-runtime parity and measured browser loading |
| Corpus pipeline ready | Fixture determinism, accounting, interruption recovery |
| Search ready | Real local Qdrant retrieval and held-out evaluation |
| Public preview ready | No-login browser flow on sample, explicitly labeled |
| Full corpus ready | Every eligible article accounted for, all chunks indexed |
| Public release ready | Actual URL, second device, live limits and credential boundary |
| Answer ready | Live provider check and human citation/support evaluation |
| Offline ready | Fresh restart without network, article reader and local generation |

## What to do when an agent stalls

Ask for the exact command/output and smallest failing fixture. If the problem is inside its assigned interface, have it fix that case and rerun the focused check. If it needs a schema/model/host change, bring its handback to the planner. Do not send the next agent a vague summary like “the pipeline mostly works”; give it the committed files, plan number and completion report.
