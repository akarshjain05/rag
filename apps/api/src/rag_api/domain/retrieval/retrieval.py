
from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor

retrieval_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="retrieval_worker")


from rag_api.adapters.vectorstore.embeddings import EmbeddingClient
from rag_api.domain.models import RetrievedChunk
from rag_api.schemas.schemas import QueryResponse
from rag_api.domain.retrieval.reranker import Reranker
from rag_api.adapters.vectorstore.vector_store import VectorStore

class HybridRetriever:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_store: VectorStore,
        *,
        reranker: Reranker | None = None,
        rerank_candidate_pool: int = 20,
        context_pruning_threshold: float = 0.30,
    ):
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.reranker = reranker
        self.rerank_candidate_pool = rerank_candidate_pool
        self.context_pruning_threshold = context_pruning_threshold

    async def semantic_cache_get(self, query: str, conversation_id: str | None = None, document_filter: list[str] | None = None, chunking_strategy: str | None = None) -> QueryResponse | None:
        try:
            query_embedding = await asyncio.get_running_loop().run_in_executor(retrieval_executor, self.embedding_client.embed, [query])
            query_vector = query_embedding[0]
            
            from functools import partial
            func = partial(
                self.vector_store.semantic_cache_get,
                query_vector,
                0.95,
                ttl_seconds=604800,
                conversation_id=conversation_id,
                document_filter=document_filter,
                chunking_strategy=chunking_strategy
            )
            # Enforce a strict timeout; if vector store hangs, bypass cache immediately
            future = asyncio.get_running_loop().run_in_executor(retrieval_executor, func)
            res = await asyncio.wait_for(future, timeout=0.25)
            return QueryResponse(**res) if res else None
        except asyncio.TimeoutError:
            import logging
            logging.getLogger(__name__).warning("Semantic cache GET timed out (degrading to cache miss)")
            return None
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Semantic cache GET failed (degrading to cache miss): {e}")
            return None

    async def semantic_cache_set(self, query: str, response: QueryResponse, conversation_id: str | None = None, document_filter: list[str] | None = None, chunking_strategy: str | None = None) -> None:
        try:
            query_embedding = await asyncio.get_running_loop().run_in_executor(retrieval_executor, self.embedding_client.embed, [query])
            query_vector = query_embedding[0]
            
            from functools import partial
            func = partial(
                self.vector_store.semantic_cache_set,
                query,
                query_vector,
                response.model_dump(mode="json"),
                conversation_id=conversation_id,
                document_filter=document_filter,
                chunking_strategy=chunking_strategy
            )
            await asyncio.get_running_loop().run_in_executor(retrieval_executor, func)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Semantic cache SET failed: {e}")

    async def retrieve_async(
        self,
        query: str,
        top_k: int = 5,
        chunking_strategy: str | None = None,
        *,
        dense_only: bool = False,
        original_query: str | None = None,
        document_filter: list[str] | None = None,
        temporal_filter: dict | None = None,
    ) -> list[RetrievedChunk]:
        query_embedding = await asyncio.get_running_loop().run_in_executor(retrieval_executor, self.embedding_client.embed, [query])
        query_embedding = query_embedding[0]
        
        where = {"chunking_strategy": chunking_strategy} if chunking_strategy else None
        if document_filter:
            where = where or {}
            where["source_document"] = document_filter

        from functools import partial
        if dense_only:
            func = partial(self.vector_store.query, query_embedding, top_k=top_k, where=where, temporal_filter=temporal_filter)
            dense = await asyncio.get_running_loop().run_in_executor(retrieval_executor, func)
            return [
                RetrievedChunk(
                    chunk_id=r["chunk_id"],
                    text=r["text"],
                    metadata=r["metadata"],
                    dense_rank=i,
                    dense_similarity=r["similarity"],
                    fused_score=r["similarity"],
                )
                for i, r in enumerate(dense[:top_k], start=1)
            ]
            
        fusion_pool_size = max(self.rerank_candidate_pool, top_k) if self.reranker else top_k
        
        # Native Qdrant Hybrid Search!
        func = partial(
            self.vector_store.hybrid_search,
            query_text=query, 
            dense_vector=query_embedding, 
            top_k=fusion_pool_size, 
            where=where,
            temporal_filter=temporal_filter
        )
        fused_dicts = await asyncio.get_running_loop().run_in_executor(retrieval_executor, func)
        
        fused = [
            RetrievedChunk(
                chunk_id=r["chunk_id"],
                text=r["text"],
                metadata=r["metadata"],
                fused_score=r.get("similarity", 0.0),
                dense_similarity=r.get("similarity")
            )
            for r in fused_dicts
        ]

        if self.reranker is None:
            return fused[:top_k]
            
        rerank_query = original_query if original_query else query
        reranked_chunks = await asyncio.get_running_loop().run_in_executor(retrieval_executor, self.reranker.rerank, rerank_query, fused, fusion_pool_size)
        
        # Hard Cutoff Threshold: Drop chunks that the reranker identified as mathematically irrelevant.
        pruned_chunks = [chunk for chunk in reranked_chunks if chunk.rerank_score is not None and chunk.rerank_score >= self.context_pruning_threshold]

        # Enforce document diversity: max 2 chunks per document so a single doc doesn't squeeze out multi-hop context
        final_chunks = []
        doc_counts = {}
        for chunk in pruned_chunks:
            doc = chunk.metadata.get("source_document", "unknown")
            if doc_counts.get(doc, 0) < 2:
                final_chunks.append(chunk)
                doc_counts[doc] = doc_counts.get(doc, 0) + 1
            if len(final_chunks) == top_k:
                break

        return final_chunks

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        chunking_strategy: str | None = None,
        *,
        dense_only: bool = False,
        original_query: str | None = None,
    ) -> list[RetrievedChunk]:
        """Synchronous wrapper for eval/script usage ONLY. Never call from FastAPI."""
        try:
            asyncio.get_running_loop()
            has_loop = True
        except RuntimeError:
            has_loop = False
            
        if has_loop:
            raise RuntimeError("HybridRetriever.retrieve() must not be called from inside an event loop. Use retrieve_async().")
            
        return asyncio.run(
            self.retrieve_async(
                query, 
                top_k=top_k, 
                chunking_strategy=chunking_strategy, 
                dense_only=dense_only, 
                original_query=original_query
            )
        )
