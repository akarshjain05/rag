from fastapi import Request
from rag_api.main import limiter
from rag_api.core.logging import log
from fastapi import APIRouter, Depends, Request, BackgroundTasks
import sentry_sdk
from rag_api.schemas.schemas import QueryRequest, QueryResponse, SourceSchema
from rag_api.api.deps import get_retriever, get_generator, run_or_502, run_or_502_async, get_conversation_store, get_llm_client, get_settings, get_vector_store, get_normalizer_llm_client
from rag_api.core.settings import Settings
from rag_api.services.query_condensation import condense_query, expand_query, generate_hyde, normalize_query, should_expand_query, expand_query, generate_hyde
from rag_api.services.conversation import Turn
from rag_api.domain.generation.generation import build_sources

router = APIRouter(prefix="/ask", tags=["query"])

@router.post("", response_model=QueryResponse, summary="Ask a question over the indexed documents", description="Hybrid dense+sparse retrieval, fused (and optionally reranked), then a grounded, cited answer. Response includes retrieval/citation/completeness confidence sub-scores and a composite. Set `compare_dense_only` to also retrieve with dense search alone, for side-by-side comparison against the hybrid result actually used to generate the answer.")
async def ask(
    request: Request,
    payload: QueryRequest,
    background_tasks: BackgroundTasks,
    retriever = Depends(get_retriever),
    generator = Depends(get_generator),
    vector_store = Depends(get_vector_store),
    store = Depends(get_conversation_store),
    llm_client = Depends(get_llm_client),
    normalizer_llm_client = Depends(get_normalizer_llm_client),
    settings: Settings = Depends(get_settings)
) -> QueryResponse:
    strategy_value = payload.chunking_strategy.value if payload.chunking_strategy else None
    
    history = []
    if payload.conversation_id:
        history = store.get_history(payload.conversation_id)
        
    search_query = payload.question
    
    # Semantic Cache Check
    import asyncio
    query_embedding = await asyncio.to_thread(retriever.embedding_client.embed, [search_query])
    query_vector = query_embedding[0]
    cached_payload = await asyncio.to_thread(vector_store.semantic_cache_get, query_vector, 0.95)
    if cached_payload:
        print("Semantic Cache Hit! Bypassing pipeline.")
        return QueryResponse(**cached_payload)

    # Step 1 (proactive): fix spelling/typos and expand obvious acronyms
    # before anything else touches the query. Retrieval, condensation, and
    # HyDE all then operate on clean text -- a typo would otherwise corrupt
    # dense embeddings, BM25 tokens, and (most severely) the cross-encoder
    # reranker's token-level comparison identically.
    temporal_filter = None
    normalize_enabled = payload.query_normalization_enabled if payload.query_normalization_enabled is not None else settings.query_normalization_enabled
    if normalizer_llm_client and normalize_enabled:
        with sentry_sdk.start_span(op="llm_request", description="Proactive Normalizer"):
            norm_result = run_or_502(normalize_query, search_query, normalizer_llm_client)
        if isinstance(norm_result, dict):
            search_query = norm_result.get("clean_query", search_query)
            # Support both the old schema and the new target_date schema
            if "target_date" in norm_result and norm_result["target_date"]:
                temporal_filter = {"target_date": norm_result["target_date"]}
            else:
                temporal_filter = norm_result.get("temporal_filter")
        else:
            search_query = norm_result

    condense_enabled = payload.query_condensation_enabled if payload.query_condensation_enabled is not None else settings.query_condensation_enabled
    if history and llm_client and condense_enabled:
        search_query = run_or_502(condense_query, search_query, history, llm_client)
        
    llm_history = [{"role": "user", "content": t.user} for t in history] + [{"role": "assistant", "content": t.assistant} for t in history]
    # We want user, assistant, user, assistant interleaved!
    llm_history = []
    for t in history:
        llm_history.append({"role": "user", "content": t.user})
        llm_history.append({"role": "assistant", "content": t.assistant})

    # 0. HyDE (Hypothetical Document Embeddings)
    # Generate a hypothetical answer to the query to maximize vector overlap
    hyde_doc = ""
    hyde_enabled = payload.hyde_enabled if payload.hyde_enabled is not None else settings.hyde_enabled
    if llm_client and hyde_enabled:
        hyde_doc = run_or_502(generate_hyde, search_query, llm_client)
    
    hyde_search_query = f"{search_query}\n\n{hyde_doc}" if hyde_doc else search_query

    import logging; logging.warning('STARTING RETRIEVE ASYNC...'); chunks = await run_or_502_async(
        retriever.retrieve_async(
            hyde_search_query, 
            top_k=payload.top_k, 
            chunking_strategy=strategy_value,
            original_query=search_query,
            document_filter=payload.document_filter
        )
    ); import logging; logging.warning('RETRIEVE ASYNC DONE')
    
    # 1. Corrective RAG (CRAG) Routing
    if retriever.reranker and chunks and llm_client:
        max_retries = settings.crag_max_retries
        retries = 0
        crag_enabled = payload.crag_expansion_enabled if payload.crag_expansion_enabled is not None else settings.crag_expansion_enabled
        while retries < max_retries and crag_enabled:
            max_score = max([c.rerank_score or 0.0 for c in chunks])
            # The query was already spell-checked in Step 1, so a low score
            # here reflects a genuine knowledge/vocabulary gap, not a
            # garbled token comparison -- safe to give a near-zero score the
            # same one-shot expansion attempt as a merely ambiguous one.
            if should_expand_query(max_score):
                log.info("crag.expansion_triggered", original_score=max_score, query=search_query, retry=retries+1, max_retries=max_retries)
                expanded_query = run_or_502(expand_query, search_query, llm_client)
                crag_chunks = await run_or_502_async(
                    retriever.retrieve_async(
                        expanded_query, 
                        top_k=payload.top_k, 
                        chunking_strategy=strategy_value,
                        original_query=search_query,
                        document_filter=payload.document_filter,
                        temporal_filter=temporal_filter
                    )
                )
                new_max_score = max([c.rerank_score or 0.0 for c in crag_chunks]) if crag_chunks else 0.0
                
                # If the expanded query found better chunks, use them!
                if new_max_score > max_score:
                    chunks = crag_chunks
                    search_query = expanded_query # use the expanded query for the LLM generation too
                else:
                    break # Expansion didn't help, break to avoid useless loop
            else:
                break # Score is either very high (good) or very low (refuse), no need to expand
            retries += 1

    # Note: Dynamic Context Pruning happens inside the generator now!

    result = run_or_502(generator.generate, search_query, chunks, image_url=payload.image_url, history=llm_history, verify_citations=payload.verify_citations)
    
    cid = payload.conversation_id or store.create_conversation()
    sources_dicts = [SourceSchema(**s).model_dump(mode="json") for s in result.sources]
    confidence_info = {
        "retrieval": float(result.retrieval_confidence) if result.retrieval_confidence is not None else None,
        "citation": float(result.citation_coverage) if result.citation_coverage is not None else None,
        "completeness": float(result.completeness) if result.completeness is not None else None,
        "composite": float(result.composite_confidence) if result.composite_confidence is not None else None
    }
    
    if await request.is_disconnected():
        return QueryResponse(conversation_id=cid, answer="[Discarded]", mode="hybrid", sources=[], used_citation_markers=[], invalid_citation_markers=[], unsupported_citation_markers=[], retrieval_confidence=0, citation_coverage=0, completeness=0, composite_confidence=0, dense_only_sources=None)
        
    store.append_turn(cid, Turn(user=payload.question, assistant=result.answer, sources=sources_dicts, confidence_info=confidence_info))
    
    dense_only_sources = None
    if payload.compare_dense_only:
        dense_chunks = await run_or_502_async(
            retriever.retrieve_async(search_query, top_k=payload.top_k, chunking_strategy=strategy_value, dense_only=True, document_filter=payload.document_filter, temporal_filter=temporal_filter)
        )
        dense_only_sources = [SourceSchema(**s) for s in build_sources(dense_chunks)]

    store.log_query_metrics(float(result.retrieval_confidence) if result.retrieval_confidence is not None else 0.0)

    response_obj = QueryResponse(
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
    
    # Save to Semantic Cache asynchronously using BackgroundTasks
    # so the user doesn't wait for the database write
    if result.mode in ("llm", "extractive"):
        def save_to_cache():
            vector_store.semantic_cache_set(payload.question, query_vector, response_obj.model_dump(mode="json"))
        background_tasks.add_task(save_to_cache)
        
    return response_obj
