
from __future__ import annotations
import asyncio


from rag_api.adapters.vectorstore.embeddings import EmbeddingClient
from rag_api.domain.models import RetrievedChunk
from rag_api.domain.retrieval.reranker import Reranker
from rag_api.adapters.vectorstore.vector_store import VectorStore

class HybridRetriever:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_store: VectorStore,
        *,
        dense_top_k: int = 10,
        sparse_top_k: int = 10,
        rrf_k: int = 60,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
        reranker: Reranker | None = None,
        rerank_candidate_pool: int = 20,
    ):
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.dense_top_k = dense_top_k
        self.sparse_top_k = sparse_top_k
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.reranker = reranker
        self.rerank_candidate_pool = rerank_candidate_pool

    import asyncio
    async def semantic_cache_get(self, query: str, conversation_id: str | None = None, document_filter: list[str] | None = None, chunking_strategy: str | None = None) -> dict | None:
        import asyncio
        query_embedding = await asyncio.get_running_loop().run_in_executor(retrieval_executor, self.embedding_client.embed, [query])
        query_vector = query_embedding[0]
        return await asyncio.get_running_loop().run_in_executor(retrieval_executor, 
            self.vector_store.semantic_cache_get,
            query_vector,
            0.95,
            ttl_seconds=604800,
            conversation_id=conversation_id,
            document_filter=document_filter,
            chunking_strategy=chunking_strategy
        )

    async def semantic_cache_set(self, query: str, response: dict, conversation_id: str | None = None, document_filter: list[str] | None = None, chunking_strategy: str | None = None) -> None:
        import asyncio
        query_embedding = await asyncio.get_running_loop().run_in_executor(retrieval_executor, self.embedding_client.embed, [query])
        query_vector = query_embedding[0]
        await asyncio.get_running_loop().run_in_executor(retrieval_executor, 
            self.vector_store.semantic_cache_set,
            query,
            query_vector,
            response,
            conversation_id=conversation_id,
            document_filter=document_filter,
            chunking_strategy=chunking_strategy
        )

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

        if dense_only:
            dense = await asyncio.get_running_loop().run_in_executor(retrieval_executor, self.vector_store.query, query_embedding, top_k=self.dense_top_k, where=where, temporal_filter=temporal_filter)
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
        fused_dicts = await asyncio.get_running_loop().run_in_executor(retrieval_executor, 
            self.vector_store.hybrid_search,
            query_text=query, 
            dense_vector=query_embedding, 
            top_k=fusion_pool_size, 
            where=where,
            temporal_filter=temporal_filter
        )
        
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
        return await asyncio.get_running_loop().run_in_executor(retrieval_executor, self.reranker.rerank, rerank_query, fused, top_k)

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
        import asyncio
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
