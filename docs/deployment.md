# Quickstart: Docker Compose

The fastest path to a running API, vector store, and dashboard,
pre-seeded with a sample corpus.

```bash
cp .env.example .env        # fill in OPENAI_API_KEY / ANTHROPIC_API_KEY
docker compose up --build
```

- Dashboard: http://localhost:5173
- API: http://localhost:8000 (interactive docs at `/docs`)

The `seed` service ingests a bundled sample corpus
(`eval/golden_corpus/`, 8 fictional company policy documents)
automatically on first startup, so the dashboard has real content to
query immediately.

## Zero-API-key demo mode

Every provider has a free path, so the full ingest → retrieve → answer
loop runs with no paid API keys at all:

```bash
pip install -r requirements-local.txt   # adds sentence-transformers
EMBEDDING_PROVIDER=local LLM_PROVIDER=none uvicorn main:app --reload
```

`LLM_PROVIDER=none` skips the LLM entirely and returns the top retrieved
chunk verbatim as an extractive answer (`"mode": "extractive"` in the
response) — useful for demoing retrieval quality on its own, or in CI,
without spending API credits.

## Local dev (API only, no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # requirements.txt + pytest/httpx
cp .env.example .env
uvicorn main:app --reload
python scripts/seed_corpus.py         # optional; SEED_API_URL=http://localhost:8000
```

## Local dev (dashboard only, against an already-running API)

```bash
cd apps/web
npm install
npm run dev          # proxies /v1 + /health to localhost:8000
```

## If ingestion silently does nothing / falls back to embedded storage

Confirm the `api` service is actually reaching Qdrant rather than
silently falling back to embedded storage due to an environment-variable
name mismatch — run `docker compose config` and check that the
resolved `api` service's environment matches what `Settings` expects.
See [`../architecture/05-known-architecture-gaps.md`](05-known-architecture-gaps.md)
for the specific known mismatch and its fix.

## Troubleshooting checklist

1. `docker compose config` — verify env vars actually reach the
   container you expect.
2. `curl localhost:8000/health` — confirm `status: "ok"` and a sane
   `embedding_provider`/`llm_provider`.
3. `curl -X POST localhost:8000/v1/ingest -F "files=@somefile.md"` —
   confirm `chunks_inserted > 0` and `error: null`.
4. `curl -X POST localhost:8000/v1/ask -d '{"question": "..."}'` —
   confirm `mode` isn't unexpectedly `"no_context"`.
5. `docker compose logs api` / `docker compose logs qdrant` for anything
   obviously wrong (connection refused, dimension mismatch errors).
# Configuration Reference

All settings live in `rag_api/core/settings.py` (`pydantic-settings`),
overridable via environment variable or a `.env` file. Names below are
the Python field names — the corresponding env var is the same name
upper-cased (e.g. `embedding_provider` → `EMBEDDING_PROVIDER`).

## Embeddings

| Field | Default | Notes |
|---|---|---|
| `embedding_provider` | `openai` | `openai` or `local` |
| `openai_embedding_model` | `text-embedding-3-small` | 1536-dim |
| `local_embedding_model` | `sentence-transformers/all-MiniLM-L6-v2` | 384-dim, free, CPU |
| `openai_api_key` | `None` | required if `embedding_provider=openai` |

## Generation

| Field | Default | Notes |
|---|---|---|
| `llm_provider` | `anthropic` | `anthropic`, `openai`, or `none` (extractive fallback, zero API keys) |
| `anthropic_model` | `claude-sonnet-4-5` | — |
| `openai_llm_model` | `gpt-4o` | — |
| `anthropic_api_key` | `None` | required if `llm_provider=anthropic` |

## Storage

| Field | Default | Notes |
|---|---|---|
| `qdrant_mode` | `embedded` | **naming legacy from the pre-Qdrant migration** — see below |
| `qdrant_persist_dir` | `./data/qdrant` | used when `qdrant_mode=embedded` |
| `qdrant_host` / `qdrant_port` | `qdrantdb` / `8000` | used when `qdrant_mode=http`; docker-compose currently sets `QDRANT_HOST`/`QDRANT_PORT` instead, which these fields do **not** read — a known mismatch, see [`../architecture/05-known-architecture-gaps.md`](05-known-architecture-gaps.md) |
| `collection_name` | `internal_docs` | Qdrant collection name |

## Chunking

| Field | Default |
|---|---|
| `default_chunking_strategy` | `structure_aware` |
| `fixed_chunk_size` / `fixed_chunk_overlap` | `1000` / `150` |
| `structure_max_section_size` / `structure_min_section_size` | `1200` / `40` |
| `semantic_similarity_threshold` | `0.55` |
| `semantic_max_chunk_chars` / `semantic_min_chunk_chars` | `1500` / `200` |
| `structure_aware_semantic_fallback_enabled` | `true` |

## PDF extraction

| Field | Default |
|---|---|
| `pdf_extraction_backend` | `pdfplumber` (`pdfplumber` \| `pymupdf`) |
| `pdf_heading_font_ratio` | `1.15` |
| `pdf_max_heading_levels` | `3` |
| `pdf_table_extraction_enabled` | `true` |
| `image_indexing_enabled` | `false` — when true, routes through the pypdfium2 loader with OCR fallback |
| `scanned_page_text_threshold` | `20` |
| `ocr_engine` / `ocr_dpi` | `tesseract` / `300` |

## Deduplication

| Field | Default |
|---|---|
| `dedup_similarity_threshold` | `0.95` |

## Retrieval

| Field | Default | Status |
|---|---|---|
| `dense_top_k` / `sparse_top_k` | `150` / `150` | **`sparse_top_k` currently unread** — Qdrant's hybrid prefetch is hardcoded to `limit=60` internally |
| `hybrid_top_k` | `5` | — |
| `rrf_k` | `60` | **currently unread** — RRF constant is Qdrant's internal default, not settings-driven |
| `rrf_dense_weight` / `rrf_sparse_weight` | `1.0` / `1.0` | **currently unread** |

## Reranking

| Field | Default |
|---|---|
| `reranker_provider` | `cross_encoder` (`none` \| `cross_encoder` \| `llm_judge`) |
| `reranker_model` | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| `rerank_candidate_pool` | `150` |

## Generation quality

| Field | Default |
|---|---|
| `citation_verification_enabled` | `true` — no-ops automatically without an LLM client |
| `citation_verification_strictness` | `lenient` (`lenient` \| `strict`) |
| `low_confidence_threshold` | `0.3` |
| `llm_request_timeout_seconds` | `30.0` |

## API

| Field | Default | Notes |
|---|---|---|
| `api_port` | `8000` | — |
| `cors_origins` | `["*"]` | **must be scoped before any non-local deployment** — see [`../security/01-current-posture.md`](01-current-posture.md) |

## A note on the `qdrant_*` naming

These fields predate the migration to Qdrant and were never renamed.
They still function (Qdrant client construction reads them), but the
name is misleading and — more importantly — doesn't match the
`QDRANT_*` environment variables `docker-compose.yml` actually sets. See
the architecture gaps doc for the concrete fix (rename the fields, or
add pydantic env-var aliases, and update `.env.example` to match).
# Deployment

## Current `docker-compose.yml` services

| Service | Image/build | Purpose |
|---|---|---|
| `qdrant` | `qdrant/qdrant:latest` | vector store; healthcheck via TCP probe on 6333 |
| `api` | `apps/api` | FastAPI app; depends on `qdrant` being healthy |
| `seed` | `apps/api`, `command: python scripts/seed_corpus.py` | one-shot: ingests the bundled sample corpus once `api` is healthy, then exits. Safe to re-run — checks first |
| `frontend` | `apps/web` | nginx serving the built React app, proxying `/v1` and `/health` to `api` |

Host ports are configurable via `.env`: `API_PORT` (default 8000),
`FRONTEND_PORT` (default 5173).

## Planned additions (large-file ingestion — see the guide)

| Service | Purpose |
|---|---|
| `redis` | Celery broker + result backend |
| `minio` | S3-compatible object storage for uploaded large files |
| `worker` | Celery worker, same image as `api`, running the streaming ingestion task |

## Required environment variables

At minimum: one embedding provider's key (`OPENAI_API_KEY` if
`EMBEDDING_PROVIDER=openai`) and one LLM provider's key
(`ANTHROPIC_API_KEY` or `OPENAI_API_KEY` depending on `LLM_PROVIDER`).
Full list: [`../guides/02-configuration-reference.md`](02-configuration-reference.md).

**Before relying on `docker compose up` alone:** confirm with
`docker compose config` that the `api` service's resolved environment
actually reaches Qdrant — there is a known naming mismatch between the
`QDRANT_*` vars compose sets and the `qdrant_*` settings fields the app
currently reads. See
[`../architecture/05-known-architecture-gaps.md`](05-known-architecture-gaps.md).

## Horizontal scaling — not yet safe

**Do not run more than one `api` replica today.** Two pieces of state
currently live in the API process's memory rather than a shared store:

- `ConversationStore` (`rag_api/services/conversation.py`) — an
  in-process `dict`. A follow-up question in the same conversation can
  land on a different replica and lose all prior history.
- `LocalImageStore` — writes extracted images to the container's local
  disk. An image ingested on one replica is unreachable from another,
  and doesn't survive a redeploy.

Both need a shared backend (Redis for conversations, S3/MinIO for
images) before running multiple replicas or doing rolling deploys
without user-visible breakage. Planned fix: see the roadmap in
[`04-known-issues-and-roadmap.md`](./04-known-issues-and-roadmap.md).

## Healthchecks

`GET /health` reports `status`, indexed chunk count, and active
provider/feature configuration — suitable for a load balancer or
orchestrator healthcheck once the app is otherwise ready for multi-replica
deployment.

## Data persistence

Qdrant's storage is a named Docker volume (`qdrant_data`) — back this up
like any production database volume. There is no automatic snapshot/
backup step configured; add one before this holds anything you can't
afford to lose or re-ingest from source documents.
# Observability

## Current state

Debug output goes to stdout via bare `print()` calls, found in:

- `rag_api/services/query_condensation.py` — logs condensed queries,
  HyDE documents, CRAG expanded queries
- `rag_api/services/ingest_service.py` — logs contextual-retrieval
  progress and per-chunk failures
- `rag_api/domain/generation/generation.py` — logs the full generator
  prompt and conversation history on every call

These are useful signal but not structured, not leveled, and will spam
container logs in production (the generation-prompt dump in particular
logs the full context block on every single request). There is no
tracing and no metrics collection today.

## Planned: structured logging

Replace `print()` with `structlog`, configured once in `create_app()`:

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
)
log = structlog.get_logger()
```

Call sites become structured, filterable events instead of string dumps:

```python
log.info("contextual_retrieval.chunk_situated", chunk_id=c.chunk_id, source=doc.source_file)
log.info("crag.expansion_triggered", original_score=max_score, query=search_query)
```

## Planned: distributed tracing

OpenTelemetry spans around each pipeline stage, so a slow `/v1/ask` call
is diagnosable by stage rather than a single opaque request duration:

```python
from opentelemetry import trace
tracer = trace.get_tracer("rag_api")

with tracer.start_as_current_span("retrieval.hybrid_search"):
    chunks = await retriever.retrieve_async(...)
with tracer.start_as_current_span("generation.llm_call"):
    result = generator.generate(...)
```

Instrument at minimum: query condensation, HyDE, hybrid retrieval,
reranking, CRAG expansion (including the re-retrieval it triggers),
generation, and citation verification — these are exactly the stages
that can chain into five sequential LLM calls per request, and the ones
most worth being able to see individually.

## Planned: metrics

`prometheus-fastapi-instrumentator` for request-level HTTP metrics, plus
custom counters/histograms at each LLM call site:

```python
from prometheus_client import Counter, Histogram

llm_calls_total = Counter("rag_llm_calls_total", "LLM calls by pipeline stage", ["stage", "provider"])
llm_call_seconds = Histogram("rag_llm_call_seconds", "LLM call latency by stage", ["stage"])
retrieval_confidence = Histogram("rag_retrieval_confidence", "Distribution of retrieval confidence scores")
```

This is the data source for cost governance (deciding which optional
LLM stages are worth keeping on by default — see
[`04-known-issues-and-roadmap.md`](./04-known-issues-and-roadmap.md))
and for catching confidence-score drift after a chunking or embedding
model change.

## Planned: error tracking and alerting

Sentry (or equivalent) SDK initialization in `main.py`. Suggested first
alert rules: `/health` failing, elevated 5xx rate on `/v1/ask`, Qdrant
connection errors, and LLM-provider error rate (provider errors already
surface as clean `502`s via `run_or_502` — the gap is alerting on the
*rate* of those, not just logging each one).
