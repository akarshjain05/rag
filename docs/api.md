# API Endpoints Reference

Base URL: same-origin, versioned business endpoints under `/v1`;
`/health` is intentionally unversioned (infra tooling — Docker
`HEALTHCHECK`, load balancers — conventionally expects a stable,
version-independent path). Interactive docs at `/docs`; raw OpenAPI
schema at `/openapi.json`.

## `GET /health`

Status, indexed chunk count, and which providers/features are active.

```bash
curl localhost:8000/health
```

```json
{
  "status": "ok",
  "indexed_chunks": 412,
  "embedding_provider": "openai",
  "llm_provider": "anthropic",
  "llm_mode": "llm",
  "reranker_provider": "cross_encoder",
  "citation_verification_enabled": true,
  "low_confidence_threshold": 0.3
}
```

## `POST /v1/ingest`

Multipart file upload, repeatable `files` field. Accepts `.md`,
`.markdown`, `.txt`, `.html`, `.htm`, `.pdf`, `.docx`, `.pptx`, `.xlsx`.
Optional `?chunking_strategy=` query param overrides the configured
default for this call. One broken file does not fail the whole batch —
check each report's `error` field.

```bash
curl -X POST localhost:8000/v1/ingest \
  -F "files=@handbook.md" -F "files=@onboarding.pdf"
```

```json
{
  "reports": [
    {"source_file": "handbook.md", "chunking_strategy": "structure_aware",
     "chunks_created": 6, "chunks_inserted": 6, "duplicates_skipped": 0, "error": null}
  ]
}
```

## `POST /v1/ask`

Hybrid retrieval (fused, optionally reranked), then a grounded, cited
answer.

```bash
curl -X POST localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many vacation days do employees accrue per month?", "top_k": 5}'
```

| Field | Type | Notes |
|---|---|---|
| `question` | string, required | — |
| `conversation_id` | string, optional | omit to start a new conversation; the response echoes back the ID to use on follow-ups |
| `verify_citations` | bool, optional | overrides the server default for this call only |
| `top_k` | int, 1–20, default 5 | — |
| `chunking_strategy` | enum, optional | filter retrieval to chunks produced by one strategy |
| `compare_dense_only` | bool, default false | also retrieves with dense search alone (no sparse, no fusion, no reranking) and returns it in `dense_only_sources`, for side-by-side comparison. Only one answer is generated either way |
| `image_url` | string, optional | analyze an image alongside the text context |

Full response shape: [`03-request-response-schemas.md`](./03-request-response-schemas.md).
`mode` is one of `"llm"`, `"extractive"`, `"low_confidence"`, or `"no_context"`.

## `GET /v1/documents`

Distinct ingested source documents and total chunk count.

## `DELETE /v1/documents/{source_document}`

Removes every chunk (across all chunking strategies) belonging to
`source_document` from the index.

> **Known issue:** the response's `chunks_deleted` count is currently
> always `1` regardless of how many chunks were actually removed — see
> [`../architecture/05-known-architecture-gaps.md`](05-known-architecture-gaps.md).

## `GET /v1/images/{image_hash}`

Serves a previously-extracted embedded image by content hash.
Image storage during ingestion is currently disabled by a pipeline bug
(see gaps doc) — this endpoint has no images to serve until that's fixed.

## Planned: `POST /v1/ingest/large` and `GET /v1/ingest/jobs/{job_id}`

Not implemented yet. For files too large to process synchronously inside
a request: upload → object storage → enqueue a background job → `202`
with a `job_id`; poll `GET /v1/ingest/jobs/{job_id}` for status/progress.
Design: [`../guides/04-large-file-ingestion.md`](04-large-file-ingestion.md).
# Authentication

## Current state

**None.** Every route is open — `/v1/ingest`, `/v1/ask`, and
`DELETE /v1/documents/{source_document}` all accept unauthenticated
requests, and `cors_origins` defaults to `["*"]`. This is acceptable for
local development only. See
[`../security/01-current-posture.md`](01-current-posture.md)
for the full list of what this implies, and
[`../security/02-authentication-and-access-control.md`](02-authentication-and-access-control.md)
for the remediation plan.

## Planned: API-key authentication

A shared-secret header check, gating every `/v1/*` route via a
router-level FastAPI dependency:

```
X-API-Key: <key>
```

Configuration: `api_keys: list[str]` in `Settings` (empty list = auth
disabled — intended for local dev only, never for a deployed
environment). Requests with a missing or unrecognized key receive `401`.

This is deliberately the simplest thing that gates access. If
per-customer identity, scoped permissions, or token expiry are required,
the natural upgrade path is OAuth2 / JWT bearer tokens on top of the same
dependency-injection point — the route wiring does not need to change,
only the `verify_api_key` dependency's implementation.

## CORS

`cors_origins` should be set to the exact origin(s) the dashboard is
served from in any non-local environment — never `["*"]` once
credentials or an API key are in play, since a wildcard origin combined
with permissive methods/headers defeats the purpose of the key check for
browser-based callers.

## Rate limiting (planned)

`/v1/ask` is the most expensive route — up to five sequential LLM calls
per request in the worst case (condensation + HyDE + CRAG expansion +
generation + citation verification). A per-key or per-IP rate limit
(e.g. `slowapi`) is planned ahead of any public exposure.
# Request / Response Schemas

Source: `rag_api/schemas/schemas.py` (pydantic — the HTTP contract layer;
kept separate from the plain-dataclass pipeline models in
`domain/models.py`).

## `QueryRequest`

| Field | Type | Default | Notes |
|---|---|---|---|
| `question` | `str` | required, min length 1 | — |
| `conversation_id` | `str \| None` | `None` | — |
| `verify_citations` | `bool \| None` | `None` | `None` = use server default (`citation_verification_enabled`) |
| `top_k` | `int` | `5` | bounded `1..20` |
| `chunking_strategy` | `ChunkingStrategy \| None` | `None` | `fixed_size` \| `structure_aware` \| `semantic` |
| `compare_dense_only` | `bool` | `False` | — |
| `image_url` | `str \| None` | `None` | — |

## `QueryResponse`

| Field | Type | Notes |
|---|---|---|
| `conversation_id` | `str \| None` | echoed back / newly created |
| `answer` | `str` | — |
| `mode` | `str` | `"llm"` \| `"extractive"` \| `"low_confidence"` \| `"no_context"` |
| `sources` | `list[SourceSchema]` | every retrieved chunk actually used to build the prompt, in citation order |
| `used_citation_markers` | `list[int]` | structurally valid `[N]` markers found in the answer |
| `invalid_citation_markers` | `list[int]` | `[N]` markers with no matching excerpt (structural check) |
| `unsupported_citation_markers` | `list[int]` | in-range markers whose excerpt was judged not to support the claim (semantic check, only populated when verification ran) |
| `retrieval_confidence` | `float \| None` | `[0,1]` |
| `citation_coverage` | `float \| None` | `[0,1]` |
| `citation_coverage_basis` | `str \| None` | `"verified"` \| `"structural"` \| `"extractive"` |
| `completeness` | `float \| None` | `[0,1]`, only when verification ran |
| `composite_confidence` | `float \| None` | weighted mean of the three sub-scores above |
| `dense_only_sources` | `list[SourceSchema] \| None` | only populated when `compare_dense_only: true` |

## `SourceSchema`

| Field | Type | Notes |
|---|---|---|
| `marker` | `int` | the `[N]` this source corresponds to |
| `chunk_id` | `str` | `{source}::{strategy}::{index}` |
| `text` | `str \| None` | — |
| `source_document` | `str \| None` | — |
| `section_heading` | `str \| None` | — |
| `page_number` | `int \| None` | PDF/PPTX only |
| `content_type` | `str \| None` | `"text"` or one of the image content types |
| `image_url` | `str \| None` | `/v1/images/{hash}` if this chunk carries an image |
| `dense_rank` | `int \| None` | — |
| `sparse_rank` | `int \| None` | `None` when the chunk came from dense-only retrieval |
| `rerank_score` | `float \| None` | `None` when no reranker is configured |

## `IngestResponse` / `IngestReportSchema`

| Field | Type | Notes |
|---|---|---|
| `source_file` | `str` | — |
| `chunking_strategy` | `str` | — |
| `chunks_created` | `int` | before dedup |
| `chunks_inserted` | `int` | after dedup |
| `duplicates_skipped` | `int` | — |
| `duplicate_of` | `list[str]` | chunk IDs the skipped duplicates matched |
| `error` | `str \| None` | non-null means this file failed; other files in the same batch still succeed independently |

## `DocumentsResponse`

`source_documents: list[str]`, `total_chunks: int`.

## `DeleteResponse`

`source_document: str`, `chunks_deleted: int` (currently always reports
`1` — see [`../architecture/05-known-architecture-gaps.md`](05-known-architecture-gaps.md)).

## `HealthResponse`

`status`, `indexed_chunks`, `embedding_provider`, `llm_provider`,
`llm_mode`, `reranker_provider`, `citation_verification_enabled`,
`low_confidence_threshold`.
