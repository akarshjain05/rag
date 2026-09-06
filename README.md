# RAG Pipeline with Hybrid Search Over Internal Docs

A retrieval-augmented generation system that ingests internal documentation
(Markdown, HTML, plaintext, PDF, Word, PowerPoint, Excel), indexes it with both dense vector search
and BM25 keyword search, fuses and reranks the candidates, and answers
questions with inline `[1]`, `[2]` citations that are validated against the
retrieved context — not just asserted.

## Architecture

```
 documents (.md/.txt/.html/.pdf/.docx/.pptx/.xlsx)
        │
        ▼
 ┌───────────────┐   normalize to plaintext + metadata
 │   loaders.py  │   (source file, section heading, page number)
 └───────┬───────┘
         ▼
 ┌───────────────┐   3 switchable strategies: fixed_size / structure_aware / semantic
 │  chunking.py  │   every chunk tagged with which strategy produced it
 └───────┬───────┘
         ▼
 ┌───────────────┐   embed (OpenAI or local) → check near-dup (cosine > 0.95)
 │  pipeline.py  │
 └───────┬───────┘
         ▼
 ┌────────────────────────────────────────┐
 │               Qdrant                   │
 │ Single Collection natively fusing:     │
 │  - Dense Embeddings                    │
 │  - FastEmbed BM25 Sparse Embeddings    │
 └───────┬────────────────────────────────┘
         │   Native Reciprocal Rank Fusion
         ▼
 ┌────────────────┐
 │  retrieval.py  │  → pool of ~20
 └───────┬────────┘
                                              ▼
                                     ┌────────────────┐
                                     │  reranker.py   │  optional: cross-encoder or
                                     └────────┬───────┘  LLM-as-judge → top 5
                                              ▼
                                     ┌────────────────┐
                                     │ generation.py  │  grounded answer + citations
                                     └────────┬───────┘
                                              ▼
                                     ┌────────────────┐
                                     │verification.py │  optional: LLM-judge checks each
                                     └────────┬───────┘  claim against its cited excerpt
                                              ▼
                                     ┌────────────────┐
                                     │ confidence.py  │  retrieval + coverage + completeness
                                     └────────────────┘  → composite score, or "I don't know"
```

`app/models.py` holds the plain-dataclass core (no FastAPI/pydantic), so the
pipeline works as a library or script; `app/api.py` + `app/schemas.py` are
the HTTP layer on top of it; `frontend/` is a React console on top of that.

**Deployment shape** (`docker compose up`): six services — `qdrant`, `redis`, `minio`, `worker`
(its own container, so storage isn't tied to the API's lifecycle),
`api`, a one-shot `seed` job that ingests the sample corpus once `api` is
healthy, and `frontend` (nginx serving the built React app, proxying `/v1`
and `/health` to `api`). `VectorStore` itself doesn't care which mode it's
in — see "Configuration" below.

## Quickstart

### Docker Compose (fastest path — API, Qdrant, Workers, and the dashboard, pre-seeded)

```bash
cp .env.example .env        # fill in OPENAI_API_KEY / ANTHROPIC_API_KEY
docker compose up --build
```

- Dashboard: http://localhost:5173
- API: http://localhost:8000 (docs at `/docs`)

The `seed` service ingests the bundled sample corpus (`eval/golden_corpus/`,
8 fictional company policy docs) automatically on first startup, so the
dashboard has real content to query immediately — no manual ingest step.

### Local dev (API only, no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # includes requirements.txt + pytest/httpx
cp .env.example .env                  # fill in API keys
uvicorn main:app --reload
python scripts/seed_corpus.py         # optional: seed the sample corpus (SEED_API_URL=http://localhost:8000)
```

### Local dev (dashboard only, against an already-running API)

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /v1 + /health to localhost:8000
```

### Zero-API-key demo mode

Every provider has a free path, so the whole ingest → retrieve → answer loop
runs with no paid API keys at all:

```bash
pip install -r requirements-local.txt   # adds sentence-transformers
EMBEDDING_PROVIDER=local LLM_PROVIDER=none uvicorn main:app --reload
```

`LLM_PROVIDER=none` skips the LLM entirely and returns the top retrieved
chunk verbatim as an extractive answer (clearly marked `"mode": "extractive"`
in the response) — useful for demoing retrieval quality on its own, or for
CI, without spending API credits.

## Configuration

Every setting lives in `app/config.py` and is overridable via env var or
`.env` — see `.env.example` for the full list with comments. The ones you'll
actually touch:

| Variable | Default | Notes |
|---|---|---|
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `local` |
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `openai`, or `none` |
| `QDRANT_MODE` | `embedded` | `embedded` (in-process, local dir) or `http` (separate Qdrant server — what docker-compose uses) |
| `DEFAULT_CHUNKING_STRATEGY` | `structure_aware` | `fixed_size`, `structure_aware`, or `semantic` |
| `DEDUP_SIMILARITY_THRESHOLD` | `0.95` | cosine similarity above which a chunk is skipped as a near-duplicate |
| `RERANKER_PROVIDER` | `none` | `none`, `cross_encoder`, or `llm_judge` — optional second-pass reranking |
| `CITATION_VERIFICATION_ENABLED` | `true` | LLM-as-judge claim verification; no-ops automatically without an LLM client |
| `LOW_CONFIDENCE_THRESHOLD` | `0.3` | retrieval confidence below this returns a structured "I don't know" instead of generating |
| `API_PORT` / `FRONTEND_PORT` | `8000` / `5173` | host ports, in case either is already taken by another local project |

## API

Business endpoints are versioned under `/v1`; `/health` stays unversioned
(infra tooling — Docker `HEALTHCHECK`, load balancers — conventionally
expects a stable, version-independent path).

| Endpoint | Description |
|---|---|
| `GET /health` | status, indexed chunk count, active providers |
| `POST /v1/ingest` | multipart file upload (repeatable `files` field); optional `?chunking_strategy=` query param |
| `POST /v1/ask` | `{question, top_k, chunking_strategy?, compare_dense_only?}` → cited answer + confidence + sources |
| `GET /v1/documents` | distinct ingested source documents + total chunk count |
| `DELETE /v1/documents/{source_document}` | remove all chunks for one document from both indexes |

Full interactive OpenAPI docs (Swagger UI) at `/docs` once the server is
running; raw schema at `/openapi.json`.

```bash
curl -X POST localhost:8000/v1/ingest \
  -F "files=@handbook.md" -F "files=@onboarding.pdf"

curl -X POST localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many vacation days do employees accrue per month?", "top_k": 5}'
```

A `/v1/ask` response looks like:

```json
{
  "answer": "Employees accrue vacation at a rate of 1.5 days per month [1].",
  "mode": "llm",
  "sources": [{
    "marker": 1, "source_document": "handbook.md", "section_heading": "Vacation Policy",
    "page_number": null, "dense_rank": 1, "sparse_rank": 2, "rerank_score": null
  }],
  "used_citation_markers": [1],
  "invalid_citation_markers": [],
  "unsupported_citation_markers": [],
  "retrieval_confidence": 0.83,
  "citation_coverage": 1.0,
  "citation_coverage_basis": "verified",
  "completeness": 0.9,
  "composite_confidence": 0.91,
  "dense_only_sources": null
}
```

`mode` is one of `"llm"`, `"extractive"`, `"low_confidence"`, or `"no_context"`.
`invalid_citation_markers` is *structural* validation (does `[N]` even refer
to a real excerpt); `unsupported_citation_markers` is *semantic* validation
(does the excerpt actually support the specific claim it's attached to) —
see "Citation verification & confidence" below. `dense_only_sources` is
populated only when the request sets `compare_dense_only: true` — see
"Dashboard" below.

## Dashboard

A React console (`frontend/`) for exploring the system interactively:

- Ask a question and see the generated answer with **clickable citation
  markers** — click `[1]` and the page scrolls to and highlights that
  source card.
- **Confidence broken down by dimension** — retrieval confidence, citation
  coverage (labeled with its basis), completeness, and the composite, each
  as its own meter, not just one opaque number.
- **Retrieved sources, ranked**, each showing its dense rank, sparse rank,
  and rerank score (whichever apply) — so it's visible *why* a chunk
  surfaced, not just that it did.
- A **hybrid vs. dense-only comparison toggle**: re-runs retrieval with
  dense search alone (no sparse, no fusion, no reranking) and shows both
  ranked lists side by side, each in its own color, next to the hybrid
  result actually used to generate the answer. Only one answer is
  generated either way — the toggle compares *retrieval*, not two separate
  LLM calls.

Talks to the API via same-origin relative paths (`/v1/...`, `/health`) —
proxied by Vite in dev (`vite.config.js`) and by nginx in the built/
containerized version (`frontend/nginx.conf`), so there's no API URL to
configure or CORS setup to get right in either case.

## Chunking strategies

- **`fixed_size`** — `RecursiveCharacterTextSplitter`, configurable size/overlap. The baseline.
- **`structure_aware`** — splits on `#`..`######` headers first (so a chunk never straddles two sections), then recursively sub-splits any section still over `STRUCTURE_MAX_SECTION_SIZE`. Every chunk carries its heading.
- **`semantic`** — splits into sentences, embeds each one, and cuts a new chunk wherever consecutive-sentence cosine similarity drops below `SEMANTIC_SIMILARITY_THRESHOLD` (a topic boundary), bounded by min/max chunk-size safety nets.

Every chunk is tagged with `chunking_strategy` in its metadata, and the same
document can be ingested more than once under different strategies without
colliding (chunk IDs are `{source}::{strategy}::{index}`) — so you can
compare retrieval quality across strategies on the same corpus. That's what
`eval/run_retrieval_eval.py --chunking-strategy` is for.

## Hybrid retrieval

Dense (cosine similarity in Qdrant) and sparse (BM25 keyword match) are
fused with **Reciprocal Rank Fusion** rather than a weighted blend of raw
scores — the two scales aren't comparable (bounded cosine similarity vs.
unbounded BM25), so blending by rank position avoids needing per-corpus
tuning to stop one signal from dominating. Per-ranker weighting
(`RRF_DENSE_WEIGHT` / `RRF_SPARSE_WEIGHT`) is still exposed as a knob on top
of that — defaults to 1.0/1.0 (equal), but e.g. weighting sparse higher
suits documentation heavy on exact function names, config keys, or error
codes that dense search tends to miss. See the docstring in
`app/retrieval.py` for the formula.

## Reranking (optional second pass)

RRF only ever sees rank position — it can't tell "shares keywords with the
question" from "actually answers it". When `RERANKER_PROVIDER` is set,
fusion produces a larger pool (`RERANK_CANDIDATE_POOL`, default 20) instead
of cutting straight to the final `top_k`, and a second pass scores that pool
directly against the query text before cutting it down:

- `cross_encoder` — a small local cross-encoder model (`RERANKER_MODEL`,
  default `cross-encoder/ms-marco-MiniLM-L-6-v2`). Free, no API key, needs
  `pip install -r requirements-local.txt`.
- `llm_judge` — a single batched call to whichever `LLM_PROVIDER` is already
  configured, asking it to score every pooled candidate at once (not one
  call per candidate — an N-times-slower judge would make the cost/latency
  trade against a cross-encoder pointless before it starts). A response
  the model didn't format as asked degrades to the original fusion order
  rather than raising.

Off by default (`RERANKER_PROVIDER=none`) — either backend is a real added
cost or dependency, so it's opt-in. `/query` responses include each source's
`dense_rank`, `sparse_rank`, and `rerank_score` (when applicable) for
visibility into which signal actually surfaced each result.

## Citation verification & confidence scoring

Structural citation validation (`invalid_citation_markers`, in every
response) only catches a hallucinated citation *number* — `[7]` when only 4
excerpts exist. It says nothing about whether an in-range citation is
actually *right*. `CITATION_VERIFICATION_ENABLED` (default on, whenever an
LLM is available) adds a second, semantic check: `app/verification.py`
splits the generated answer into sentence-level claims, sends every
claim + the excerpt(s) it cited to an LLM judge in **one** batched call
(not one call per claim), and flags any claim the judge says its citation
doesn't actually support in `unsupported_citation_markers`. An in-range but
unsupported citation is exactly the failure mode structural validation
can't see.

The same call also rates answer **completeness** (0–1, does the answer
address every part of the question). Combined with **retrieval
confidence** (mean dense cosine similarity of the returned chunks) and
**citation coverage** (fraction of claims well-cited), `composite_confidence`
is a plain unweighted mean of whichever of the three are available —
returned as-is rather than dressed up as a calibrated probability, with all
three sub-scores still broken out individually for anyone who wants a
different weighting. `citation_coverage_basis` says which basis coverage was
computed on: `"verified"` (a judge actually checked support), `"structural"`
(no judge ran — only "has a citation at all" is checkable), or
`"extractive"` (trivially 1.0 — the whole answer *is* the cited chunk,
verbatim).

**Graceful "I don't know"**: when retrieval confidence falls below
`LOW_CONFIDENCE_THRESHOLD` (default 0.3), `mode` becomes `"low_confidence"`
and generation is skipped entirely — no LLM call spent on a query that's
going to be flagged as insufficient anyway. The response still names which
documents came closest and suggests checking them manually, rather than
just saying no:

```json
{
  "answer": "I don't have confident enough information in the indexed documents to answer this reliably (retrieval confidence 0.17 is below the 0.30 threshold). The closest matches were in: handbook.md. You may want to check those documents manually, or rephrase the question.",
  "mode": "low_confidence",
  "retrieval_confidence": 0.17
}
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                          # 226 tests
pytest --cov=app --cov-report=term-missing   # coverage, 98%
```

External providers (OpenAI, Anthropic, sentence-transformers) are mocked at
the SDK boundary — tests verify this codebase's logic, not third-party
services, and run with no network access and no API keys. Everything that
doesn't touch a paid API (loaders, all three chunkers, dedup, BM25/Qdrant
sync, weighted RRF fusion, both rerankers, structural + semantic citation
validation, confidence scoring, the eval framework's judges and
aggregation, the full FastAPI surface) is exercised against real Qdrant +
real BM25 + a deterministic fake embedder, not just asserted against mocks.

## Retrieval eval harness

```bash
python eval/run_retrieval_eval.py --sample
```

Ingests a small bundled corpus and reports Recall@k / MRR for dense-only,
sparse-only, and hybrid retrieval side by side — the quantitative case for
hybrid search on its own, without generation in the loop. Point it at your
own corpus with `--dataset queries.json --docs-dir ./my_docs` (dataset is a
JSON list of `{"query": "...", "expected_source": "filename.md"}`).

## Golden Q&A eval suite

The harness above answers "did we find the right chunks?" — it says
nothing about whether the *generated answer* was any good. This is the
broader framework: a hand-written 57-question golden dataset run through
the real retrieve-then-generate pipeline, scored on four metrics.

```bash
python eval/run_eval_suite.py                          # needs a real LLM -- no zero-key mode for this one
python eval/run_eval_suite.py --compare-chunking-strategies
```

**The dataset** (`eval/golden_qa.json`, evaluated against
`eval/golden_corpus/` — 8 fictional company policy documents) has 57
hand-written examples across four categories:

| Category | Count | What it tests |
|---|---|---|
| `lookup` | 24 | a straightforward single-fact answer in one document |
| `multi_hop` | 16 | answering correctly requires combining two documents |
| `unanswerable` | 9 | plausible-sounding, but genuinely not covered by the corpus — correct behavior is declining, not fabricating |
| `ambiguous` | 8 | genuinely underspecified or has more than one reasonable reading — correct behavior is surfacing that, not confidently guessing one facet |

**The four metrics**, computed per case in `eval/judges.py` and `eval/metrics.py`:

- **Answer correctness** — LLM-as-judge comparing the generated answer
  against the golden answer. Category-aware: for `unanswerable` examples,
  correct means the system declined rather than fabricated; for
  `ambiguous` examples, correct means the answer surfaces the ambiguity or
  clearly answers one reasonable reading, not that it silently assumed the
  only possible one.
- **Faithfulness** — a *different* check from Phase 3's runtime citation
  verification. Citation accuracy (below) only checks claims that already
  carry a citation marker, against their own cited excerpt. Faithfulness
  checks **every** claim — cited or not — against the **full** retrieved
  context, in one batched LLM-judge call. An uncited, hallucinated claim
  slipped in alongside otherwise-correct cited claims is exactly the gap
  citation accuracy alone can't see.
- **Retrieval relevance** — recall of `expected_source_documents` (each
  golden example says which document(s) the answer should come from) among
  what was actually retrieved. `None`, not 0.0, for `unanswerable`
  examples, which have nothing correct to retrieve — forcing a number
  there would silently corrupt the average for every question that *does*
  have a real answer to find.
- **Citation accuracy** — read directly off the live pipeline's own
  `citation_coverage` (verified basis) from Phase 3. No separate
  computation; the eval suite exercises the same production code path a
  real query would hit, not a parallel reimplementation of it.

**The chunking strategy comparison** (`--compare-chunking-strategies`)
ingests `golden_corpus/` under all three strategies into the same
collection — safe, since chunk IDs are namespaced
`{source}::{strategy}::{index}` (`app/models.py`) — then runs the full
57-question suite once per strategy, filtering retrieval to that
strategy's chunks each time via the same `chunking_strategy` filter
`/query` exposes. Output is a side-by-side table plus which strategy wins
on which metric — concrete, corpus-specific numbers instead of a general
claim that one chunking strategy is "better."

Every LLM-judge call in the eval framework is a single batched call per
case (one for correctness, one for faithfulness), same discipline as the
reranker and citation verifier — 57 examples means at most ~114 judge
calls for a full run, not 114 × (number of claims per answer).

## Known limitations / design tradeoffs

Documented here rather than hidden, since knowing the edges of a system is
part of building it honestly:

- **PDF headings**: We use `pymupdf` or `pdfplumber` to synthesize markdown headings based on font size and alphanumeric density. This captures document structure without fragmenting Table of Contents entries or page numbers, though it may miss semantic headings that are identically sized to body text.
- **Excel (.xlsx) Table Splitting**: Spreadsheets are loaded one section per
  sheet and serialized as markdown tables. The `RecursiveCharacterTextSplitter`
  will cut a large markdown table mid-row-block, meaning later chunks lose
  the header row context. This is fine for small/medium sheets, but large sheets
  would require a dedicated row-aware chunker for perfect results.
- **Unified Indexing**: The pipeline now uses Qdrant for both dense and sparse (BM25) storage, eliminating the need for parallel SQLite/Chroma synchronization.
- **Sentence splitting** for semantic chunking is regex-based (punctuation +
  capital letter), not a real sentence tokenizer — it will mis-split on
  abbreviations (`e.g.`, `Dr.`) in adversarial text. Fine for typical prose;
  swap in spaCy/nltk if your corpus is abbreviation-heavy.
- **Citation verification checks structure, not truth**: it catches a
  hallucinated citation *number* (`[7]` when only 4 excerpts exist), not a
  subtly wrong paraphrase of a real excerpt. Full claim-level grounding
  would need an NLI-style verification pass — noted as a natural next step,
  not implemented here.
- **LLM-as-judge reranking is one batched call**, which keeps latency sane
  but leans on the model's instruction-following to return well-formed JSON
  for the whole pool at once; scoring degrades gracefully (falls back to
  fusion order) rather than failing, but a very large `RERANK_CANDIDATE_POOL`
  on a weak model is more likely to trigger that fallback. `cross_encoder`
  doesn't have this failure mode.
- **Retrieval confidence is Calibrated Exponential Decay**. Using top-K weighting, the system ensures that long-tail noise doesn't drag down the confidence of a perfectly retrieved top-1 chunk.
  probability.** A sparse-only hit (no dense signal at all) contributes 0.0
  to that mean, which is a deliberate choice — dense search considering
  something irrelevant is itself meaningful — but it means retrieval
  confidence is a consistent ordinal signal for *this system*, not a
  cross-system-comparable probability.
- **Citation verification is one batched call, same trade-off as the
  reranker's LLM judge**: fast and cheap relative to per-claim calls, but a
  malformed response degrades to "couldn't verify" (`supported: None`, not
  `False`) rather than raising — check `citation_coverage_basis` if a
  response's coverage looks unexpectedly low.
- **The golden Q&A dataset is hand-written against a fictional corpus**,
  not real internal documentation. It exercises the eval framework
  honestly (facts are cross-checked against the actual corpus text, not
  invented independently), but "57 examples, 4 categories" is a template
  and a starting point for a much larger real dataset, not a claim that 57
  examples is enough coverage for a production system.
- **Eval-suite metric ties break on strategy declaration order**: if two
  chunking strategies score identically on a metric (more likely on a
  small dataset or with the deterministic fake embedder than with a real
  one), `format_comparison_report` reports whichever was listed first as
  the "winner" — standard `max()` behavior, not a hidden tiebreak rule,
  but worth knowing before reading a report from a very small eval run.
- **The database layer runs on Qdrant**, providing native Reciprocal Rank Fusion via its Rust engine instead of doing math in Python memory.
  image as documented, but wasn't pulled and run in *this* build
  environment** (network-restricted to package registries, not Docker Hub).
  What *is* directly verified: `VectorStore(mode="http")` against a real,
  locally-launched Qdrant server (`tests/test_vector_store.py`), which
  exercises the exact same `qdrant_client.QdrantClient` code path the compose
  service would use — so the client-side wiring is solid even though the
  container image itself wasn't pulled here. Worth a sanity check
  (`docker compose up`, `curl localhost:8000/health`) after first pulling
  the image in your own environment, in case the image's default port or
  healthcheck path has moved since.
- **`npm audit` flags two vulnerabilities in `esbuild`/`vite`** (moderate
  and high) — both are dev-server-only (`vite dev` accepting requests from
  any origin), don't affect the production build output nginx actually
  serves, and only matter if the dev server is exposed to an untrusted
  network. Not patched here since the fix (`vite@8`) is a breaking major
  version bump out of scope for this pass; run `npm audit fix --force` in
  `frontend/` if you want it and are prepared to re-verify the dev server
  still runs.

## Project structure

```
app/
  loaders.py         multi-format document loading + normalization
  chunking.py         3 chunking strategies
  text_utils.py       shared sentence splitter (chunking + claim parsing)
  embeddings.py       OpenAI / local / fake embedding clients
  vector_store.py     Qdrant client and Hybrid Search (Prefetch + FusionQuery)
  dedup.py            near-duplicate detection
  pipeline.py          ingestion orchestration
  retrieval.py        async orchestration mapping to Qdrant native hybrid search
  reranker.py         cross-encoder / LLM-as-judge reranking
  llm_client.py       Anthropic / OpenAI client wrappers
  generation.py       grounded answer generation + low-confidence path
  verification.py     LLM-as-judge citation verification
  confidence.py       composite confidence scoring
  api.py / schemas.py / config.py / models.py
eval/
  run_retrieval_eval.py    retrieval-only recall@k / MRR harness
  golden_dataset.py         golden Q&A schema + loader
  golden_qa.json            57 hand-written examples
  golden_corpus/            8 fictional policy docs the dataset is written against
  judges.py                 LLM-as-judge: answer correctness, faithfulness
  metrics.py                retrieval relevance + result aggregation
  eval_runner.py             suite orchestration + chunking strategy comparison
  run_eval_suite.py          CLI entrypoint
scripts/
  seed_corpus.py         ingests eval/golden_corpus/ via the API -- the docker-compose `seed` service
frontend/               React dashboard (Vite) -- see "Dashboard" above
  src/components/         Sidebar, QueryPanel, AnswerPanel, ConfidenceBreakdown, SourcesList
  src/api.js               fetch wrapper (same-origin relative paths)
  Dockerfile / nginx.conf   multi-stage build -> nginx, proxying /v1 + /health to `api`
tests/                 226 tests, mocked at the external-API boundary
```
# rag
