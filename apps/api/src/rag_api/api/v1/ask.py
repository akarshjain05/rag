from fastapi import APIRouter, Depends
from rag_api.schemas.schemas import QueryRequest, QueryResponse, SourceSchema
from rag_api.api.deps import get_retriever, get_generator, run_or_502
from rag_api.domain.generation.generation import build_sources

router = APIRouter(prefix="/ask", tags=["query"])

@router.post("", response_model=QueryResponse, summary="Ask a question over the indexed documents", description="Hybrid dense+sparse retrieval, fused (and optionally reranked), then a grounded, cited answer. Response includes retrieval/citation/completeness confidence sub-scores and a composite. Set `compare_dense_only` to also retrieve with dense search alone, for side-by-side comparison against the hybrid result actually used to generate the answer.")
def ask(
    payload: QueryRequest,
    retriever = Depends(get_retriever),
    generator = Depends(get_generator)
) -> QueryResponse:
    strategy_value = payload.chunking_strategy.value if payload.chunking_strategy else None
    
    chunks = run_or_502(retriever.retrieve, payload.question, top_k=payload.top_k, chunking_strategy=strategy_value)
    result = run_or_502(generator.generate, payload.question, chunks, image_url=payload.image_url)
    
    dense_only_sources = None
    if payload.compare_dense_only:
        dense_chunks = run_or_502(
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
