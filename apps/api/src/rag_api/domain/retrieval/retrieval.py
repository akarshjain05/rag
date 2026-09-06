
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
    async def retrieve_async(
        self,
        query: str,
        top_k: int = 5,
        chunking_strategy: str | None = None,
        *,
        dense_only: bool = False,
        original_query: str | None = None,
        document_filter: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        import logging; logging.warning('EMBEDDING...'); query_embedding = await asyncio.to_thread(self.embedding_client.embed, [query]); import logging; logging.warning('EMBEDDING DONE')
        query_embedding = query_embedding[0]
        
        where = {"chunking_strategy": chunking_strategy} if chunking_strategy else None

        if dense_only:
            dense = await asyncio.to_thread(self.vector_store.query, query_embedding, top_k=self.dense_top_k, where=where)
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
        import logging; logging.warning('HYBRID SEARCH...'); fused_dicts = self.vector_store.hybrid_search(
            query, 
            query_embedding, 
            top_k=fusion_pool_size, 
            where=where
        ); import logging; logging.warning('HYBRID SEARCH DONE')
        
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
        return await asyncio.to_thread(self.reranker.rerank, rerank_query, fused, top_k)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        chunking_strategy: str | None = None,
        *,
        dense_only: bool = False,
        original_query: str | None = None,
    ) -> list[RetrievedChunk]:
        # Synchronous wrapper over the new hybrid_search logic
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(
            self.retrieve_async(
                query, 
                top_k=top_k, 
                chunking_strategy=chunking_strategy, 
                dense_only=dense_only, 
                original_query=original_query
            )
        )
