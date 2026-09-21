# Research and implementation references

Checked 2026-09-15. Documentation can change; these links are evidence for the choices, not a promise of future prices. Package APIs must be checked against versions locked in plan 001.

## Hosting

- [Qdrant free cluster](https://qdrant.tech/documentation/cloud/create-cluster/): 1 GB RAM, 4 GB disk, 0.5 vCPU, one node; suspension/deletion on inactivity. Preserve portable artifacts independently of cloud.
- [Qdrant pricing](https://qdrant.tech/pricing/): prototype tier; real capacity and load must be measured.
- [Qdrant database authentication](https://qdrant.tech/documentation/cloud/authentication/): read-only collection scope and key expiration.
- [Qdrant storage](https://qdrant.tech/documentation/manage-data/storage/): on-disk storage choices.
- [Qdrant API reference](https://api.qdrant.tech/): validate collection creation, point query, payload projection and snapshots for chosen server/client versions.
- [Workers limits](https://developers.cloudflare.com/workers/platform/limits/): free HTTP CPU budget 10 ms, 128 MB memory, 100,000 requests/day; 25 MiB individual static asset limit at review time.
- [Workers static assets](https://developers.cloudflare.com/workers/static-assets/): single deployment for static UI and API.
- [Workers rate limit binding](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/): local-to-datacenter, eventually consistent, not exact accounting.
- [Workers secrets](https://developers.cloudflare.com/workers/configuration/secrets/): keep Qdrant credential server-side.

## Corpus and embeddings

- [Simple English latest dump listing](https://dumps.wikimedia.org/simplewiki/latest/): observed September 2026 pages-articles.xml.bz2 is 356,186,307 bytes; multistream variant 385,846,687 bytes. Download regular variant for simpler sequential parsing. Resolve a dated complete dump during implementation; the dated directory could not be retrieved by this planning browser.
- [mwxml](https://github.com/mediawiki-utilities/python-mwxml): streaming dump reader; verify current XML schema compatibility.
- [mwparserfromhell docs](https://mwparserfromhell.readthedocs.io/en/latest/): markup AST. Parsing templates does not render/expand their definitions.
- [BGE author model card](https://huggingface.co/BAAI/bge-small-en-v1.5): 384 dimensions, 512-token context, query instruction, CLS pooling and L2 normalization.
- [BGE pooling configuration](https://huggingface.co/BAAI/bge-small-en-v1.5/blob/main/1_Pooling/config.json): inspect and pin actual pooling settings.
- [ONNX conversion card](https://huggingface.co/Xenova/bge-small-en-v1.5): browser-compatible artifact. Its mean-pooling example differs from the author's CLS instructions; plan 002 must resolve this with config inspection and parity checks, not by copying the example unchanged.
- [Transformers.js](https://huggingface.co/docs/transformers.js/en/index): browser/Node inference, model revisions, WASM/device and dtype configuration.

## Generation, local mode and reuse

- [Gemini text generation](https://ai.google.dev/gemini-api/docs/text-generation): REST request and response envelopes; pin a tested supported model at execution.
- [Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key): keep owner keys out of frontend builds. Visitor-entered keys remain readable by page JavaScript, so explain tab-memory handling; do not claim a browser can protect them against a compromised page.
- [Ollama chat](https://docs.ollama.com/api/chat): local generation, stream option and structured responses.
- [pgvector](https://github.com/pgvector/pgvector): Postgres vector extension, cosine operator, HNSW, exact search and vector storage; used only by conditional plan 013.
- [Wikimedia Terms of Use, reuse section](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use/en): source attribution, license notices, modifications and exceptions.
- [Kiwix](https://kiwix.org/): optional existing offline encyclopedia reader; separate from the app's tested local SQLite reader.

## Facts versus proposed gates

Counts, build times, embedding throughput, browser model download bytes, retrieval scores and actual free-tier fit have NOT been measured in this repository. Numbers in acceptance criteria are engineering targets to test. The plan deliberately includes probes before expensive work.

