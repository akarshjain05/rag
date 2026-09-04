from fastapi import APIRouter, Depends
from rag_api.schemas.schemas import QueryRequest, QueryResponse, SourceSchema
from rag_api.api.deps import get_retriever, get_generator, run_or_502, get_conversation_store, get_llm_client
from rag_api.services.query_condensation import condense_query
from rag_api.services.conversation import Turn
from rag_api.domain.generation.generation import build_sources

router = APIRouter(prefix="/ask", tags=["query"])

@router.post("", response_model=QueryResponse, summary="Ask a question over the indexed documents", description="Hybrid dense+sparse retrieval, fused (and optionally reranked), then a grounded, cited answer. Response includes retrieval/citation/completeness confidence sub-scores and a composite. Set `compare_dense_only` to also retrieve with dense search alone, for side-by-side comparison against the hybrid result actually used to generate the answer.")
def ask(
    payload: QueryRequest,
    retriever = Depends(get_retriever),
    generator = Depends(get_generator),
    store = Depends(get_conversation_store),
    llm_client = Depends(get_llm_client)
) -> QueryResponse:
    strategy_value = payload.chunking_strategy.value if payload.chunking_strategy else None
    
    history = []
    if payload.conversation_id:
        history = store.get_history(payload.conversation_id)
        
    search_query = payload.question
    if history and llm_client:
        search_query = run_or_502(condense_query, payload.question, history, llm_client)
        
    llm_history = [{"role": "user", "content": t.user} for t in history] + [{"role": "assistant", "content": t.assistant} for t in history]
    # We want user, assistant, user, assistant interleaved!
    llm_history = []
    for t in history:
        llm_history.append({"role": "user", "content": t.user})
        llm_history.append({"role": "assistant", "content": t.assistant})

    chunks = run_or_502(retriever.retrieve, search_query, top_k=payload.top_k, chunking_strategy=strategy_value)
    result = run_or_502(generator.generate, search_query, chunks, image_url=payload.image_url, history=None, verify_citations=payload.verify_citations)
    
    cid = payload.conversation_id or store.create_conversation()
    store.append_turn(cid, Turn(user=payload.question, assistant=result.answer))
    
    dense_only_sources = None
    if payload.compare_dense_only:
        dense_chunks = run_or_502(
            retriever.retrieve, search_query, top_k=payload.top_k, chunking_strategy=strategy_value, dense_only=True
        )
        dense_only_sources = [SourceSchema(**s) for s in build_sources(dense_chunks)]

    return QueryResponse(
        conversation_id=cid,
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
