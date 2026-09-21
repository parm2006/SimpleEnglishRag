# Architecture and decisions

Planned 2026-09-15. This is a design, not an implemented system.

## Objective

A visitor opens one public URL, searches the full Simple English Wikipedia article corpus, reads cited passages without signing in, and optionally requests an LLM answer using their own Gemini key. A local edition can search and generate answers without cloud dependencies after its assets have been downloaded.

"All Simple English" means the readable main-namespace article text in one dated snapshot, including stubs and lists. It does not mean edit histories, discussion pages, every template expansion, all images, or all human knowledge. Preserve the source dump so cleaner improvements can recover omitted material. Every main-namespace page must receive a recorded disposition; a failed article cannot disappear silently.

## Fixed initial choices

| Concern | Choice | Why |
|---|---|---|
| Corpus | Dated Simple English pages-articles XML dump | Reproducible, bulk source |
| Ingestion | Python 3.12, uv, typed models, streaming parser | Suitable for data work on Windows |
| XML / markup | mwxml and mwparserfromhell, behind pure adapters | Avoid regular-expression parsing |
| Canonical content | SQLite plus original dump | Local article reader, auditability, portable rebuilds |
| Embeddings | BAAI/bge-small-en-v1.5, 384 dimensions, CLS pooling, normalized | Compact model; browser conversion available |
| Browser model | Pinned Xenova/bge-small-en-v1.5 ONNX, q8 if parity passes | Visitor computes query; no hosted inference bill |
| Vector storage | Qdrant server locally, Qdrant Cloud for public site | Same storage API |
| Public runtime | Cloudflare Worker with static assets | One origin for Vite frontend and /api routes |
| UI | React, TypeScript, Vite, ordinary CSS | Familiar tools; no SSR needed |
| Worker embedding | None | Free Worker CPU/memory is unsuitable for running this transformer |
| Public answers | Gemini REST, visitor's key in tab memory | Optional generation, no owner-funded generation |
| Local answers | Python local server to Ollama | Avoid public HTTPS page accessing localhost |
| Tests | pytest, Vitest, Playwright, real-Qdrant integration | Test contracts, retrieval, UI and failures |
| Packaging | npm workspaces, uv project, Docker Compose | Few moving parts |
| Fallback | Postgres + pgvector only if capacity gate fails | Full corpus stays in scope |

Do not add LangChain, LlamaIndex, Kubernetes, accounts, billing, a chat-history database, agents, or automatic web browsing to v1. These add no necessary capability to this product.

## Two request paths

Public search:
1. Browser gets /api/config.
2. User submits a question.
3. Dedicated browser Web Worker loads/caches pinned ONNX model and computes query embedding.
4. Browser POSTs vector + embedding contract ID + corpus ID to /api/search.
5. Cloudflare validates request, applies limits, and queries a fixed Qdrant collection.
6. Worker returns public payload fields, never vectors or database credentials.
7. Browser renders ranked passages, full chunk text and Wikipedia source links.
8. Optional Generate answer sends question + selected passages directly to Gemini.

Local search:
1. User launches Qdrant and the Python local app on loopback.
2. Local app serves built frontend and compatible config/search endpoints.
3. Query embeddings can run in Python through /api/search-text.
4. SQLite supplies complete local articles.
5. Optional /api/answer calls Ollama on loopback.
6. Downloaded corpus, model, frontend assets and runtime packages support an offline restart test.

The public application is online. Browser caching of the embedding model alone does not make the corpus available offline.

## Capacity and cost policy

Qdrant free currently advertises 1 GB RAM, 4 GB disk and 0.5 vCPU. This is a resource limit, not a guarantee that this corpus or a particular concurrency will fit. See SOURCES.md.

At 384 dimensions with float32:
- 100,000 vectors: 153,600,000 bytes of raw vectors.
- 500,000 vectors: 768,000,000 bytes.
- 1,000,000 vectors: 1,536,000,000 bytes.

These exclude payloads, graph index, segments, WAL, optimization copies, backups and free headroom. Quantization can add a second representation while retaining originals; it does not imply disk usage drops by the same factor.

Use 10,000 representative articles for a preliminary indexed measurement, then count chunks for the entire cleaned corpus before the full embedding run. Full local indexing is the final fit test. Target steady-state <=70% of actual disk quota and <=70% of RAM, peak indexing <=85%, and acceptable latency under five concurrent search clients. These are project gates, not provider promises. Snapshots and updates require separate space.

When fit fails:
1. Check accidental duplication and indexing settings.
2. Try on-disk payload/vector/HNSW settings and measure again.
3. Consider a measured quantization experiment with retrieval regression checks.
4. Do not increase inputs beyond model context or drop articles.
5. Execute conditional plan 013 for local Postgres + pgvector feasibility.
6. If no suitable free hosted capacity exists, present the measured paid-host requirement. Changing database software does not create free hosting capacity.

The owner pays no per-query embedding bill in the public design. Visitors pay download/compute cost. Gemini quota/billing belongs to each visitor. Hosting free tiers have usage limits; the site is not promised to serve unlimited concurrent visitors.

## Deliberate corrections to the old roadmap

The root wikipedia-rag-roadmap.md is historical context; these plans govern implementation:
- Public reads go through a small API from the first public release.
- Model context includes title, section, special tokens and body; 600-token chunks are invalid here.
- Browser and ingestion pooling/tokenization must match, not just vector dimensions.
- No "about 50k-250k chunks" assumption; count the complete corpus.
- No corpus pruning to claim free-tier success.
- No shared paid LLM key in the browser.
- No promise that the Worker runs an embedding model for free.
- Local release follows the public release and does not delay the initial public search milestone.

## Quality policy

Retrieval scores are ranking signals, not calibrated confidence probabilities. Always show sources, and never use a made-up universal score cutoff. Citation IDs establish which passage was referenced; they do not prove that the cited passage supports the claim. Human evaluation must check support.

Prefer honest source-only output when generation fails. Describe this as an encyclopedia search project, not verified emergency advice. Source display remains available independently of generation.

## Windows and portability

Run root commands from C:/Users/parth/Projects/SimpleEnglishRAG. Use PowerShell-compatible examples, localhost port mappings, and pathlib in Python. Avoid shell-specific pipelines in package scripts. Data and model paths accept spaces. CPU execution is the default; CUDA acceleration is optional and must not change output contracts.

