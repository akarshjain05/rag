# Architecture Overview

## What this system is

A retrieval-augmented generation (RAG) service that ingests internal
documents (Markdown, HTML, plaintext, PDF, Word, PowerPoint, Excel),
indexes them in Qdrant with both dense (embedding) and sparse (BM25)
vectors, fuses the two natively via Qdrant's Reciprocal Rank Fusion (RRF),
optionally reranks, and answers questions with inline `[1]`, `[2]`
citations that are validated against the retrieved context rather than
just asserted.

Three layers:

- **`rag_api/domain/`** — plain-dataclass pipeline logic (chunking,
  retrieval, generation, confidence scoring). No FastAPI/pydantic
  coupling, so it is usable as a library or from a script.
- **`rag_api/adapters/`** — everything that talks to an external system:
  Qdrant, embedding providers (OpenAI/local), LLM providers
  (Anthropic/OpenAI), image storage, sparse indexing.
- **`rag_api/api/`** — the FastAPI HTTP surface on top of the above.

`apps/web` is a separate React/Vite dashboard that talks to the API over
same-origin relative paths.

## Request-level pipeline

```
                      INGESTION
documents (.md/.txt/.html/.pdf/.docx/.pptx/.xlsx)
        │
        ▼
 loaders.py          normalize to plaintext + metadata
        │             (source file, section heading, page number)
        ▼
 chunking.py         fixed_size / structure_aware / semantic
        │             every chunk tagged with which strategy produced it
        ▼
 ingest_service.py   embed → dedup (cosine > threshold) → skip or insert
        │             optional: per-chunk LLM "contextual retrieval" summary
        ▼
 vector_store.py     single Qdrant collection: named dense vector +
                      FastEmbed BM25 sparse vector, upserted together


                      QUERY
User question
        │
        ▼
 [query condensation]   only if there is prior conversation history
        │
        ▼
 [HyDE]                 hypothetical-answer expansion, if an LLM is configured
        │
        ▼
 retrieval.py        Qdrant native hybrid search
                      (Prefetch dense + Prefetch sparse → FusionQuery RRF)
        │
        ▼
 [reranker.py]       optional second pass: cross-encoder or LLM-judge
        │
        ▼
 [CRAG loop]          if top rerank score is "ambiguous" (0.40–0.79),
                      expand the query with an LLM and re-retrieve once
        │
        ▼
 generation.py       grounded answer + citation markers
        │             (dynamic context pruning drops low-score chunks first)
        ▼
 verification.py     optional: LLM-judge checks each claim against
                      its cited excerpt
        │
        ▼
 confidence.py       retrieval + citation coverage + completeness
                      → composite score, or a structured "I don't know"
```

Depending on which optional stages are active, a single `/v1/ask` call can
issue up to four sequential LLM round trips (condensation, HyDE, CRAG
expansion, generation) plus a fifth for citation verification. See
[`05-known-architecture-gaps.md`](./05-known-architecture-gaps.md) and
[`../operations/04-known-issues-and-roadmap.md`](04-known-issues-and-roadmap.md)
for the plan to make each of these independently measurable and toggleable.

## Deployment shape

`docker compose up` brings up: `qdrant` (vector store), `api` (FastAPI),
a one-shot `seed` job that ingests a bundled sample corpus once `api` is
healthy, and `frontend` (nginx serving the built React app, proxying
`/v1` and `/health` to `api`).

## Related documents

- [Ingestion pipeline](./02-ingestion-pipeline.md)
- [Retrieval and generation](./03-retrieval-and-generation.md)
- [Data model](./04-data-model.md)
- [Known architecture gaps](./05-known-architecture-gaps.md)
# Ingestion Pipeline

Source: `apps/api/src/rag_api/adapters/storage/loaders.py`,
`rag_api/domain/chunking/chunking.py`, `rag_api/services/ingest_service.py`,
`rag_api/adapters/storage/dedup.py`.

## 1. Loading

`load_document()` dispatches on file extension to a format-specific
loader, and every loader returns a `LoadedDocument`: full plaintext with
markdown-style `#`..`######` heading markers, plus `pages` (populated only
for PDF/PPTX) so page-accurate metadata survives chunking.

| Extension | Loader | Notes |
|---|---|---|
| `.md`, `.markdown` | `_load_markdown` | passed through as-is; already uses `#` headings |
| `.txt` | `_load_text` | optional heuristic heading detection (ALL CAPS lines, numbered sections) behind `text_heading_detection_enabled` |
| `.html`, `.htm` | `_load_html` | `<script>`/`<style>` stripped; `<h1>`–`<h6>` converted to `#`–`######`; inline/remote images optionally OCR'd or captioned |
| `.pdf` | `_load_pdf` → one of `_load_pdf_pypdfium2` / `_load_pdf_pdfplumber` / `_load_pdf_pymupdf` | backend chosen by `pdf_extraction_backend`; pypdfium2 path is used automatically when `image_indexing_enabled=true` (adds OCR fallback + embedded image extraction) |
| `.docx` | `_load_docx` | heading styles → `#` levels; tables → markdown tables; inline images extracted best-effort |
| `.pptx` | `_load_pptx` | one page per slide; slide title becomes `# heading` |
| `.xlsx` | `_load_xlsx` | one section per sheet, serialized as a markdown table |

`load_documents()` (plural) never raises for a single bad file — it
collects `{"source_file", "error"}` entries instead, so one broken upload
doesn't abort a batch (`test_loaders.py::test_load_documents_collects_errors_instead_of_raising`).

## 2. Chunking

Three switchable strategies (`ChunkingStrategy` enum), selected via
`default_chunking_strategy` or per-request `?chunking_strategy=`:

- **`fixed_size`** — `RecursiveCharacterTextSplitter`, configurable
  `fixed_chunk_size`/`fixed_chunk_overlap`. The baseline.
- **`structure_aware`** — splits on markdown headers first (a chunk never
  straddles two sections), then recursively sub-splits any section over
  `structure_max_section_size`. Falls back to `semantic` (if an embedding
  client is available and `structure_aware_semantic_fallback_enabled` is
  true) or plain recursive splitting when the text has no headings at
  all — e.g. a plain PDF page.
- **`semantic`** — splits into sentences (`chunking/text_utils.py`'s
  regex-based splitter — not a real tokenizer, so it can mis-split on
  abbreviations like "e.g."), embeds each sentence, and cuts a new chunk
  wherever consecutive-sentence cosine similarity drops below
  `semantic_similarity_threshold`, bounded by
  `semantic_min_chunk_chars`/`semantic_max_chunk_chars`.

For PDFs and PPTX, every strategy chunks page-by-page (or slide-by-slide)
so `page_number` metadata is always exact and chunks never straddle a
page break.

Every chunk gets a deterministic ID: `{source}::{strategy}::{index}`
(`Chunk.__post_init__` in `domain/models.py`). This means:

- the same document can be ingested under multiple strategies without ID
  collisions — the basis for `eval/run_eval_suite.py --compare-chunking-strategies`
- re-ingesting the same file after a crash/retry re-produces the same IDs
  rather than creating duplicates, provided the chunking is deterministic
  for the same input text

Low-quality chunks (too short, or too low an alphabetic-character ratio —
catches stray numbers, page numbers, table-of-contents artifacts) are
filtered out and counted in `IngestReport.chunks_skipped_low_quality`.

## 3. Contextual retrieval preprocessing (optional)

When an LLM client is configured, `IngestionPipeline.ingest_file()`
generates a short "situating" summary for every chunk and prepends it to
the chunk text before embedding/indexing — Anthropic's "contextual
retrieval" technique. The **entire source document** is sent as the LLM's
`system` prompt with `cache_control: {"type": "ephemeral"}` so repeated
calls (one per chunk, run concurrently via a `ThreadPoolExecutor`) hit
Anthropic's prompt cache instead of re-billing the full document each
time.

**This does not scale to very large documents** — a multi-hundred-page or
gigabyte-scale source document sent as a system prompt will exceed every
provider's context window. See
[`../guides/04-large-file-ingestion.md`](04-large-file-ingestion.md):
the large-file ingestion path deliberately skips this stage.

## 4. Deduplication

`check_duplicate_batch()` compares each new chunk's embedding against
whatever is already in the vector store — including chunks inserted
earlier in the *same* batch — using cosine similarity against
`dedup_similarity_threshold` (default `0.95`). A hit is skipped and
recorded in `IngestReport.duplicates_skipped` / `duplicate_of`.

## 5. Indexing

Surviving chunks are upserted into Qdrant via `VectorStore.add_many()`,
which writes the dense vector and lets Qdrant's FastEmbed integration
compute and store the sparse BM25 vector from the chunk text in the same
call. See [`04-data-model.md`](./04-data-model.md) for the collection
schema.

## Large-file ingestion (planned)

For files too large to load and chunk synchronously inside the API
process, a separate streaming path is planned: the API uploads the raw
file to object storage and enqueues a background job; a worker streams
the file in bounded blocks (never materializing the whole file in
memory), chunks with `RecursiveCharacterTextSplitter`, and embeds/upserts
in small batches. Full design in
[`../guides/04-large-file-ingestion.md`](04-large-file-ingestion.md).
# Retrieval & Generation Pipeline

Source: `rag_api/domain/retrieval/retrieval.py`, `reranker.py`,
`rag_api/api/v1/ask.py`, `rag_api/domain/generation/generation.py`,
`verification.py`, `confidence.py`.

## Hybrid retrieval

`HybridRetriever.retrieve_async()` embeds the query, then calls
`VectorStore.hybrid_search()`, which issues a single Qdrant
`query_points` call with two `Prefetch` clauses (dense cosine search on
the `dense_jina` named vector, sparse BM25 search on `sparse_bm25` via
FastEmbed) fused server-side with `FusionQuery(fusion=Fusion.RRF)`. This
replaces an earlier Python-side implementation that ran dense and sparse
search separately and combined ranks in application code — the fusion
math now happens inside Qdrant's engine.

`dense_only=True` bypasses sparse search and reranking entirely — used by
the dashboard's hybrid-vs-dense-only comparison toggle
(`compare_dense_only` on `/v1/ask`).

The synchronous `HybridRetriever.retrieve()` wrapper exists for
call sites that are not `async` (e.g. the eval CLIs); the async FastAPI
endpoint should call `retrieve_async()` directly rather than going through
this wrapper — see
[`05-known-architecture-gaps.md`](./05-known-architecture-gaps.md).

## Reranking (optional)

`RERANKER_PROVIDER` selects `none` (default in some environments),
`cross_encoder` (local `sentence-transformers` cross-encoder, no API
cost), or `llm_judge` (one batched call scoring every candidate at once,
not one call per candidate). When a reranker is configured, fusion
produces a larger pool (`rerank_candidate_pool`) instead of cutting
straight to the final `top_k`.

## Query pre-processing (`/v1/ask`, all optional)

1. **Query condensation** (`query_condensation.py::condense_query`) —
   only runs if the request carries a `conversation_id` with prior
   history; rewrites a follow-up question into a standalone query.
2. **HyDE** (`generate_hyde`) — generates a hypothetical answer passage
   and appends it to the search query to improve vector-space overlap
   with the real answer.
3. **CRAG expansion loop** — after the first retrieval, if a reranker is
   configured and the top rerank score falls in `[0.40, 0.80)`
   ("ambiguous"), the query is expanded with LLM-generated synonyms/
   acronyms and retrieval is re-run once; the expanded result is kept
   only if its top score actually improved. These thresholds are
   currently hardcoded in `ask.py`, not settings-driven.

Each of these is a separate LLM call. Chained together with generation
and citation verification, a single request can issue **up to five**
sequential LLM calls. See the cost-governance plan in
[`../operations/04-known-issues-and-roadmap.md`](04-known-issues-and-roadmap.md)
(milestone M5) for making each one independently toggleable and
measured.

## Generation

`AnswerGenerator.generate()`:

- Returns `mode="no_context"` immediately if no chunks were retrieved.
- Returns `mode="low_confidence"` (skipping the LLM call entirely) if
  mean retrieval confidence falls below `low_confidence_threshold`
  (default `0.3`) — a structured "I don't know" naming the closest
  documents, not a wasted API call.
- **Dynamic context pruning**: chunks with a `rerank_score < 0.30` are
  dropped from the prompt before generation (but still returned in the
  response's `sources` list, so the UI can show what was found even if
  it wasn't used) — mitigates "lost in the middle" degradation on long
  contexts.
- In `mode="extractive"` (no LLM configured), the top chunk is returned
  verbatim with `[1]` — a zero-API-key demo path.
- In `mode="llm"`, every claim is expected to carry a `[N]` citation
  marker referencing a numbered context excerpt.

## Citation validation — two independent layers

1. **Structural** (`_extract_and_validate_citations`, always runs) — does
   citation number `[N]` even refer to a real excerpt? Catches a
   hallucinated citation *number*. Result: `invalid_citation_markers`.
2. **Semantic** (`verification.CitationVerifier`, optional, needs an LLM)
   — does excerpt `[N]` actually *support* the specific claim it's
   attached to? One batched LLM call splits the answer into sentence-level
   claims and rates each `full`/`partial`/`none` against its cited
   excerpt(s). Result: `unsupported_citation_markers`. An in-range but
   unsupported citation is exactly the failure mode structural validation
   alone cannot see.

## Confidence scoring

`confidence.py` combines three sub-scores, each already on `[0,1]`:

- **Retrieval confidence** — exponentially-decayed weighted average of
  chunk similarity/rerank scores (top-ranked chunks count more; a long
  tail of weak matches doesn't drag down a strong top hit).
- **Citation coverage** — fraction of claims judged well-cited.
  `citation_coverage_basis` reports which basis was used: `"verified"`
  (a judge actually checked support), `"structural"` (no judge ran — only
  "has a citation at all" is checkable), or `"extractive"` (trivially
  `1.0`).
- **Completeness** — 0–1 judge rating of whether the answer addresses the
  whole question (only available when citation verification ran).

`compute_composite_confidence()` combines them as a weighted average
(retrieval 50%, coverage 30%, completeness 20%), documented as exactly
that — a consistent ordinal signal for this system, not a calibrated
cross-system probability.

## Related documents

- [Data model](./04-data-model.md)
- [Tuning retrieval and reranking](05-tuning-retrieval-and-reranking.md)
- [Metrics reference](03-metrics-reference.md)
# Data Model

Source: `rag_api/domain/models.py`, `rag_api/adapters/vectorstore/vector_store.py`,
`rag_api/schemas/schemas.py`.

Core pipeline dataclasses (`domain/models.py`) are deliberately kept
separate from the FastAPI/pydantic request/response schemas
(`schemas/schemas.py`) so the pipeline has zero web-framework coupling
and can run as a library or script.

## Core dataclasses

| Type | Purpose | Key fields |
|---|---|---|
| `LoadedDocument` | Normalized loader output | `source_file`, `format`, `text`, `pages` (PDF/PPTX only), `images` |
| `PageText` | One page/slide of extracted text | `page_number` (1-indexed), `text`, `extraction_method` (`native`/`ocr`) |
| `ExtractedImage` | An embedded image found during loading | `image_hash`, `page_number`, `content_type` (`image_ocr`/`image_caption`/`image_untranscribed`), `derived_text` |
| `Chunk` | A chunk ready for embedding + indexing | `text`, `source_document`, `chunking_strategy`, `chunk_index`, `chunk_id` (derived: `{source}::{strategy}::{index}`), `section_heading`, `page_number` |
| `RetrievedChunk` | A chunk returned from retrieval, with scoring provenance | `dense_rank`, `sparse_rank`, `fused_score`, `rerank_score`, `dense_similarity` |
| `ClaimVerification` | One sentence-level claim from a generated answer | `claim_text`, `citation_markers`, `supported` (`True`/`False`/`None`=not checked), `support_level` (`full`/`partial`/`none`) |
| `IngestReport` | Per-file ingestion result | `chunks_created`, `chunks_inserted`, `duplicates_skipped`, `chunks_skipped_low_quality`, `error` |

## Qdrant collection schema

One collection (`collection_name`, default `internal_docs`) per
deployment, created with:

```python
vectors_config={
    "dense_jina": models.VectorParams(size=768, distance=models.Distance.COSINE)
}
sparse_vectors_config={
    "sparse_bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)
}
```

Every point's payload carries the full chunk metadata plus `text` and
`chunk_id` (see `Chunk.metadata()`): `source_document`, `chunk_index`,
`section_heading`, `chunking_strategy`, `char_count`, `page_number`,
`image_ref`, `content_type`, `extraction_method`.

Point IDs are a deterministic UUIDv5 derived from `chunk_id`
(`uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id)`), so re-upserting the same
logical chunk overwrites rather than duplicates.

**Known issue:** the dense vector size is hardcoded to `768` ("Jina v2"),
but neither shipped embedding provider produces 768-dimensional vectors
(OpenAI `text-embedding-3-small` = 1536, local
`all-MiniLM-L6-v2` = 384). The collection's dense-vector size must match
`embedding_client.dimension` at collection-creation time. See
[`05-known-architecture-gaps.md`](./05-known-architecture-gaps.md).

## API schemas (selected)

`QueryRequest` → `QueryResponse` is the main contract:

```
QueryRequest:  question, conversation_id?, verify_citations?, top_k (1-20),
               chunking_strategy?, compare_dense_only, image_url?

QueryResponse: answer, mode, sources[], used_citation_markers,
               invalid_citation_markers, unsupported_citation_markers,
               retrieval_confidence, citation_coverage,
               citation_coverage_basis, completeness, composite_confidence,
               dense_only_sources?
```

Full field-level reference: [`../api/03-request-response-schemas.md`](03-request-response-schemas.md).
