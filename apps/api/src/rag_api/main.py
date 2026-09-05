import uvicorn
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from rag_api.core.settings import Settings, get_settings
from rag_api.adapters.vectorstore.embeddings import EmbeddingClient, build_embedding_client
from rag_api.adapters.vectorstore.vector_store import VectorStore
from rag_api.adapters.storage.image_store import build_image_store
from rag_api.adapters.llm.llm_client import LLMClient, build_llm_client
from rag_api.domain.models import ChunkingStrategy
from rag_api.domain.retrieval.reranker import Reranker, build_reranker
from rag_api.domain.retrieval.retrieval import HybridRetriever
from rag_api.domain.generation.generation import AnswerGenerator
from rag_api.domain.generation.verification import CitationVerifier
from rag_api.services.ingest_service import IngestionPipeline
from rag_api.services.conversation import ConversationStore

from rag_api.api.v1 import documents, ask
from rag_api.schemas.schemas import HealthResponse

_UNSET = object()

def create_app(
    settings: Settings | None = None,
    *,
    embedding_client: EmbeddingClient | None = None,
    llm_client: LLMClient | None = None,
    llm_mode: str | None = None,
    vector_store: VectorStore | None = None,
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
            timeout=settings.llm_request_timeout_seconds,
        )
    llm_mode = llm_mode or ("extractive" if llm_client is None else "llm")

    if reranker is _UNSET:
        reranker = build_reranker(settings.reranker_provider, model_name=settings.reranker_model, llm_client=llm_client)

    if citation_verifier is _UNSET:
        if settings.citation_verification_enabled and llm_client is not None:
            if settings.citation_verifier_model:
                verifier_llm = build_llm_client(
                    settings.llm_provider,
                    model=settings.citation_verifier_model,
                    api_key=settings.anthropic_api_key if settings.llm_provider == "anthropic" else settings.openai_api_key,
                    base_url=settings.openai_base_url if settings.llm_provider == "openai" else None,
            timeout=settings.llm_request_timeout_seconds,
                )
            else:
                verifier_llm = llm_client
            citation_verifier = CitationVerifier(verifier_llm, strictness=settings.citation_verification_strictness)
        else:
            citation_verifier = None

    vector_store = vector_store or VectorStore(
        settings.chroma_persist_dir,
        settings.collection_name,
        mode=settings.chroma_mode,
        host=settings.chroma_host,
        port=settings.chroma_port,
    )


    image_store_instance = build_image_store(settings.image_store_backend, base_dir=settings.image_store_path)

    pipeline = IngestionPipeline(
        embedding_client,
        vector_store,
        llm_client=llm_client,
        image_store=image_store_instance,
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
        description="Ingests internal documentation, indexes it with dense + sparse hybrid search, and answers questions with grounded, cited responses.",
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
    app.state.conversation_store = ConversationStore()
    app.state.llm_client = llm_client
    app.state.image_store = image_store_instance

    @app.get("/health", response_model=HealthResponse, tags=["health"])
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
    v1.include_router(documents.router)
    v1.include_router(ask.router)
    app.include_router(v1)

    return app

app = create_app()

if __name__ == "__main__":
    load_dotenv()
    settings = get_settings()
    uvicorn.run("rag_api.main:app", host="0.0.0.0", port=settings.api_port, reload=True)
