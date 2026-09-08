from fastapi import Request
from typing import List, Dict, Optional, Any
import sentry_sdk
import logging
from rag_api.api.deps import run_or_502, run_or_502_async
from rag_api.schemas.schemas import QueryRequest, QueryResponse, SourceSchema
from rag_api.domain.models import ChunkingStrategy
from rag_api.services.conversation import Turn
from rag_api.services.query_condensation import normalize_query, condense_query, generate_hyde, expand_query, should_expand_query
from rag_api.domain.generation.generation import build_sources

log = logging.getLogger("rag_api")

class QueryOrchestrationService:
    def __init__(self, retriever, llm_client, generator, conversation_store, settings, normalizer_llm_client, background_tasks):
        self.retriever = retriever
        self.llm_client = llm_client
        self.generator = generator
        self.conversation_store = store = conversation_store
        self.settings = settings
        self.normalizer_llm_client = normalizer_llm_client
        self.background_tasks = background_tasks

    async def answer_query(self, payload: QueryRequest, request: Request) -> QueryResponse:
        store = self.conversation_store
        settings = self.settings
        retriever = self.retriever
        llm_client = self.llm_client
        generator = self.generator
        normalizer_llm_client = self.normalizer_llm_client
        
        search_query = payload.question
        
        # Semantic Cache Check
        strategy_value = payload.chunking_strategy.value if payload.chunking_strategy else None
        cached_payload = await run_or_502_async(retriever.semantic_cache_get(
            query=search_query,
            conversation_id=payload.conversation_id,
            document_filter=payload.document_filter,
            chunking_strategy=strategy_value
        ))
        if cached_payload:
            log.info("semantic_cache.hit", query=search_query)
            cached_sources = cached_payload.sources
            cid = payload.conversation_id or store.create_conversation()
            store.append_turn(cid, Turn(
                user=payload.question, 
                assistant=cached_payload.answer, 
                sources=[s.model_dump() for s in cached_sources], 
                confidence_info={
                    "retrieval": cached_payload.retrieval_confidence,
                    "coverage": cached_payload.citation_coverage,
                    "completeness": cached_payload.completeness,
                    "composite": cached_payload.composite_confidence
                }
            ))
            cached_payload.conversation_id = cid
            return cached_payload

        temporal_filter = None
        normalize_enabled = settings.query_normalization_enabled
        if normalizer_llm_client and normalize_enabled:
            with sentry_sdk.start_span(op="llm_request", description="Proactive Normalizer"):
                norm_result = await run_or_502(normalize_query, search_query, normalizer_llm_client)
            if isinstance(norm_result, dict):
                search_query = norm_result.get("clean_query", search_query)
                if norm_result.get("target_date"):
                    temporal_filter = {"target_date": norm_result["target_date"]}
            else:
                search_query = norm_result

        history = []
        if payload.conversation_id:
            history = store.get_history(payload.conversation_id)

        condense_enabled = settings.query_condensation_enabled
        if history and llm_client and condense_enabled:
            search_query = await run_or_502(condense_query, search_query, history, llm_client)
            
        llm_history = []
        for t in history:
            llm_history.append({"role": "user", "content": t.user})
            llm_history.append({"role": "assistant", "content": t.assistant})

        hyde_doc = ""
        hyde_enabled = settings.hyde_enabled
        if llm_client and hyde_enabled:
            hyde_doc = await run_or_502(generate_hyde, search_query, llm_client)
        
        hyde_search_query = f"{search_query}\n\n{hyde_doc}" if hyde_doc else search_query

        chunks = await run_or_502_async(
            retriever.retrieve_async(
                hyde_search_query, 
                top_k=payload.top_k, 
                chunking_strategy=strategy_value,
                original_query=search_query,
                document_filter=payload.document_filter,
                temporal_filter=temporal_filter
            )
        )
        
        if retriever.reranker and llm_client:
            max_retries = settings.crag_max_retries
            retries = 0
            crag_enabled = settings.crag_expansion_enabled
            while retries < max_retries and crag_enabled:
                retries += 1
                max_score = max([c.rerank_score or 0.0 for c in chunks]) if chunks else 0.0
                if should_expand_query(max_score, ceiling=settings.crag_threshold_upper):
                    log.info("crag.expansion_triggered", original_score=max_score, query=search_query, retry=retries, max_retries=max_retries)
                    expanded_query = await run_or_502(expand_query, search_query, llm_client)
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
                    
                    if new_max_score > max_score:
                        chunks = crag_chunks
                        search_query = expanded_query 
                    else:
                        break 
                else:
                    break 

        if await request.is_disconnected():
            cid = payload.conversation_id or store.create_conversation()
            return QueryResponse(conversation_id=cid, answer="[Discarded]", mode="no_context", sources=[], used_citation_markers=[], invalid_citation_markers=[], unsupported_citation_markers=[], retrieval_confidence=0, citation_coverage=0, completeness=0, composite_confidence=0, dense_only_sources=None)

        result = await run_or_502(generator.generate, search_query, chunks, image_url=payload.image_url, history=llm_history, verify_citations=payload.verify_citations)
        
        cid = payload.conversation_id or store.create_conversation()
        sources_dicts = result.sources
        confidence_info = {
            "retrieval": float(result.retrieval_confidence) if result.retrieval_confidence is not None else None,
            "citation": float(result.citation_coverage) if result.citation_coverage is not None else None,
            "completeness": float(result.completeness) if result.completeness is not None else None,
            "composite": float(result.composite_confidence) if result.composite_confidence is not None else None
        }
        
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
        
        if result.mode in ("llm", "extractive"):
            async def save_to_cache():
                await retriever.semantic_cache_set(
                    query=payload.question, 
                    response=response_obj,
                    conversation_id=payload.conversation_id,
                    document_filter=payload.document_filter,
                    chunking_strategy=strategy_value
                )
            
            self.background_tasks.add_task(save_to_cache)
            
        return response_obj
