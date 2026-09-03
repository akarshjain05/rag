"""FastAPI app.

`create_app()` is a factory rather than a bare module-level `app`, so tests
can inject fake embedding/LLM clients (or an isolated vector store) directly
at construction time instead of fighting `dependency_overrides` against
lifespan-managed state. `main.py` calls `create_app()` with no overrides for
real runs.

Business endpoints live under `/v1` (versioned, since this is meant to be a
stable API a frontend depends on); `/health` stays unversioned, since
infra tooling (Docker HEALTHCHECK, load balancers) conventionally expects a
stable, version-independent path.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from anthropic import AnthropicError
from fastapi import APIRouter, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAIError

from app.config import Settings, get_settings
from app.embeddings import EmbeddingClient, build_embedding_client
from app.generation import AnswerGenerator, build_sources
from app.llm_client import LLMClient, build_llm_client
from app.models import ChunkingStrategy
from app.pipeline import IngestionPipeline
from app.reranker import Reranker, build_reranker
from app.retrieval import HybridRetriever
from app.schemas import (
    DeleteResponse,
    DocumentsResponse,
    HealthResponse,
    IngestReportSchema,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    SourceSchema,
)
from app.sparse_index import SparseIndex
from app.vector_store import VectorStore
from app.verification import CitationVerifier

_UNSET = object()  # distinguishes "caller didn't pass reranker" from "caller passed reranker=None to force it off"


def create_app(
    settings: Settings | None = None,
    *,
    embedding_client: EmbeddingClient | None = None,
    llm_client: LLMClient | None = None,
    llm_mode: str | None = None,
    vector_store: VectorStore | None = None,
    sparse_index: SparseIndex | None = None,
    reranker: Reranker | None = _UNSET,
    citation_verifier: CitationVerifier | None = _UNSET,
) -> FastAPI:
    settings = settings or get_settings()

    embedding_client = embedding_client or build_embedding_client(
        settings.embedding_provider,
        openai_model=settings.openai_embedding_model,
        openai_api_key=settings.openai_api_key,
        openai_base_url=settings.openai_base_url,
        local_model=settings.local_embedding_model,
    )

    if llm_client is None and llm_mode is None:
        llm_client = build_llm_client(
            settings.llm_provider,
            model=settings.anthropic_model if settings.llm_provider == "anthropic" else settings.openai_llm_model,
            api_key=settings.anthropic_api_key if settings.llm_provider == "anthropic" else settings.openai_api_key,
            base_url=settings.openai_base_url if settings.llm_provider == "openai" else None,
        )
    llm_mode = llm_mode or ("extractive" if llm_client is None else "llm")

    if reranker is _UNSET:
        reranker = build_reranker(settings.reranker_provider, model_name=settings.reranker_model, llm_client=llm_client)

    if citation_verifier is _UNSET:
        citation_verifier = (
            CitationVerifier(llm_client) if settings.citation_verification_enabled and llm_client is not None else None
        )

    vector_store = vector_store or VectorStore(
        settings.chroma_persist_dir,
        settings.collection_name,
        mode=settings.chroma_mode,
        host=settings.chroma_host,
        port=settings.chroma_port,
    )
    sparse_index = sparse_index if sparse_index is not None else SparseIndex()
    sparse_index.rebuild_from(vector_store.get_all())  # BM25 has no persistence of its own; hydrate from Chroma

    pipeline = IngestionPipeline(
        embedding_client,
        vector_store,
        sparse_index,
        default_strategy=ChunkingStrategy(settings.default_chunking_strategy),
        fixed_chunk_size=settings.fixed_chunk_size,
        fixed_chunk_overlap=settings.fixed_chunk_overlap,
        structure_max_section_size=settings.structure_max_section_size,
        semantic_similarity_threshold=settings.semantic_similarity_threshold,
        semantic_max_chunk_chars=settings.semantic_max_chunk_chars,
        semantic_min_chunk_chars=settings.semantic_min_chunk_chars,
        dedup_similarity_threshold=settings.dedup_similarity_threshold,
    )
    retriever = HybridRetriever(
        embedding_client,
        vector_store,
        sparse_index,
        dense_top_k=settings.dense_top_k,
        sparse_top_k=settings.sparse_top_k,
        rrf_k=settings.rrf_k,
        dense_weight=settings.rrf_dense_weight,
        sparse_weight=settings.rrf_sparse_weight,
        reranker=reranker,
        rerank_candidate_pool=settings.rerank_candidate_pool,
    )
    generator = AnswerGenerator(
        llm_client,
        mode=llm_mode,
        citation_verifier=citation_verifier,
        low_confidence_threshold=settings.low_confidence_threshold,
    )

    app = FastAPI(
        title="RAG Pipeline with Hybrid Search Over Internal Docs",
        version="1.0.0",
        description="Ingests internal documentation, indexes it with dense + sparse hybrid "
        "search, and answers questions with grounded, cited responses.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = settings
    app.state.pipeline = pipeline
    app.state.retriever = retriever
    app.state.generator = generator
    app.state.vector_store = vector_store
    app.state.sparse_index = sparse_index

    def _run_or_502(fn, *args, **kwargs):
        """Run a call that hits an external embedding/LLM provider, turning
        SDK-level failures (bad key, rate limit, network) into a clean 502
        instead of a bare 500 with a stack trace as the only clue."""
        try:
            return fn(*args, **kwargs)
        except (OpenAIError, AnthropicError) as exc:
            raise HTTPException(status_code=502, detail=f"Upstream AI provider error: {exc}") from exc

    @app.get("/health", response_model=HealthResponse, tags=["health"], summary="Service health and active configuration")
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            indexed_chunks=vector_store.count(),
            embedding_provider=settings.embedding_provider,
            llm_provider=settings.llm_provider,
            llm_mode=llm_mode,
            reranker_provider=settings.reranker_provider,
            citation_verification_enabled=citation_verifier is not None,
            low_confidence_threshold=settings.low_confidence_threshold,
        )

    v1 = APIRouter(prefix="/v1")

    @v1.post(
        "/ingest",
        response_model=IngestResponse,
        tags=["documents"],
        summary="Ingest one or more documents",
        description="Accepts markdown, plaintext, HTML or PDF files (repeatable `files` field). Each file is "
        "loaded, chunked, embedded, deduplicated against the existing index, and added to both the dense and "
        "sparse indexes. One broken file doesn't fail the whole batch -- check each report's `error` field.",
    )
    async def ingest_documents(
        files: list[UploadFile] = File(...),
        chunking_strategy: ChunkingStrategy | None = Query(
            default=None, description="Defaults to the server's configured default strategy if omitted."
        ),
    ) -> IngestResponse:
        # Note: FastAPI's own validation already rejects a request with no
        # `files` part at all, or a part with an empty filename (422)
        # before this line runs. The `if not f.filename` check below is
        # defensive belt-and-suspenders for that case rather than a path
        # confirmed reachable through this app's own multipart validation.
        tmp_dir = Path(tempfile.mkdtemp(prefix="rag_ingest_"))
        try:
            saved_paths = []
            for f in files:
                if not f.filename:
                    continue
                dest = tmp_dir / Path(f.filename).name
                with dest.open("wb") as out:
                    shutil.copyfileobj(f.file, out)
                saved_paths.append(dest)

            if not saved_paths:
                raise HTTPException(status_code=400, detail="No valid files provided")

            reports = _run_or_502(pipeline.ingest_files, saved_paths, strategy=chunking_strategy)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return IngestResponse(reports=[IngestReportSchema(**vars(r)) for r in reports])

    @v1.post(
        "/ask",
        response_model=QueryResponse,
        tags=["query"],
        summary="Ask a question over the indexed documents",
        description="Hybrid dense+sparse retrieval, fused (and optionally reranked), then a grounded, cited "
        "answer. Response includes retrieval/citation/completeness confidence sub-scores and a composite. Set "
        "`compare_dense_only` to also retrieve with dense search alone, for side-by-side comparison against the "
        "hybrid result actually used to generate the answer.",
    )
    def ask(payload: QueryRequest) -> QueryResponse:
        print("Starting ask endpoint...")
        strategy_value = payload.chunking_strategy.value if payload.chunking_strategy else None
        
        print("Retrieving chunks...")
        chunks = _run_or_502(retriever.retrieve, payload.question, top_k=payload.top_k, chunking_strategy=strategy_value)
        print(f"Retrieved {len(chunks)} chunks.")
        
        print("Generating answer...")
        result = _run_or_502(generator.generate, payload.question, chunks, image_url=payload.image_url)
        print("Generated answer!")
        
        dense_only_sources = None
        if payload.compare_dense_only:
            dense_chunks = _run_or_502(
                retriever.retrieve, payload.question, top_k=payload.top_k, chunking_strategy=strategy_value, dense_only=True
            )
            dense_only_sources = [SourceSchema(**s) for s in build_sources(dense_chunks)]

        return QueryResponse(
            answer=result.answer,
            mode=result.mode,
            sources=[SourceSchema(**s) for s in result.sources],
            used_citation_markers=result.used_citation_markers,
            invalid_citation_markers=result.invalid_citation_markers,
            unsupported_citation_markers=result.unsupported_citation_markers,
            retrieval_confidence=result.retrieval_confidence,
            citation_coverage=result.citation_coverage,
            citation_coverage_basis=result.citation_coverage_basis,
            completeness=result.completeness,
            composite_confidence=result.composite_confidence,
            dense_only_sources=dense_only_sources,
        )

    @v1.get(
        "/documents",
        response_model=DocumentsResponse,
        tags=["documents"],
        summary="List indexed documents",
    )
    def list_documents() -> DocumentsResponse:
        return DocumentsResponse(
            source_documents=vector_store.list_source_documents(),
            total_chunks=vector_store.count(),
        )

    @v1.delete(
        "/documents/{source_document}",
        response_model=DeleteResponse,
        tags=["documents"],
        summary="Remove a document from the index",
        description="Deletes every chunk (across all chunking strategies) belonging to `source_document` from "
        "both the vector store and the sparse index.",
    )
    def delete_document(source_document: str) -> DeleteResponse:
        deleted = vector_store.delete_source_document(source_document)
        sparse_index.rebuild_from(vector_store.get_all())
        return DeleteResponse(source_document=source_document, chunks_deleted=deleted)

    app.include_router(v1)

    return app
