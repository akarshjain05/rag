"""Hybrid retrieval: dense (ChromaDB) + sparse (BM25), combined with
Reciprocal Rank Fusion (RRF), with an optional reranking pass.

RRF fuses by *rank position* rather than blending raw scores, because dense
cosine similarity and BM25 scores live on incomparable scales (bounded
[-1,1] vs. unbounded):

    score(doc) = sum over each ranker r in which doc appears of
                 weight_r * 1 / (k + rank_r(doc))

A doc that ranks well on both dense and sparse search accumulates score from
both sums and rises to the top; a doc unique to one ranker still gets a
score, just a smaller one. `k` (default 60, the value from the original RRF
paper) damps the influence of any single very-high rank. `dense_weight` /
`sparse_weight` default to 1.0/1.0 (each ranker counted equally, and no
per-corpus tuning needed) but are exposed as a tunable knob — e.g. weighting
sparse higher for technical documentation heavy on exact function names,
config keys or error codes that dense search tends to miss.

When a reranker is configured, fusion produces a larger candidate pool
(`rerank_candidate_pool`, default 20) instead of cutting straight to
`top_k`; the reranker then scores that pool against the actual query text
and returns the final `top_k`.
"""
from __future__ import annotations

from rag_api.adapters.vectorstore.embeddings import EmbeddingClient
from rag_api.domain.models import RetrievedChunk
from rag_api.domain.retrieval.reranker import Reranker
from rag_api.adapters.vectorstore.sparse_index import SparseIndex
from rag_api.adapters.vectorstore.vector_store import VectorStore


def reciprocal_rank_fusion(
    dense_results: list[dict],
    sparse_results: list[dict],
    *,
    k: int = 60,
    top_k: int = 5,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
) -> list[RetrievedChunk]:
    scores: dict[str, float] = {}
    info: dict[str, dict] = {}
    dense_rank: dict[str, int] = {}
    sparse_rank: dict[str, int] = {}

    for rank, r in enumerate(dense_results, start=1):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + dense_weight * (1.0 / (k + rank))
        info[cid] = r
        dense_rank[cid] = rank

    for rank, r in enumerate(sparse_results, start=1):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + sparse_weight * (1.0 / (k + rank))
        info.setdefault(cid, r)
        sparse_rank[cid] = rank

    ranked_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:top_k]

    return [
        RetrievedChunk(
            chunk_id=cid,
            text=info[cid]["text"],
            metadata=info[cid]["metadata"],
            dense_rank=dense_rank.get(cid),
            sparse_rank=sparse_rank.get(cid),
            fused_score=scores[cid],
            dense_similarity=info[cid].get("similarity") if cid in dense_rank else None,
        )
        for cid in ranked_ids
    ]


class HybridRetriever:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_store: VectorStore,
        sparse_index: SparseIndex,
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
        self.sparse_index = sparse_index
        self.dense_top_k = dense_top_k
        self.sparse_top_k = sparse_top_k
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.reranker = reranker
        self.rerank_candidate_pool = rerank_candidate_pool

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        chunking_strategy: str | None = None,
        *,
        dense_only: bool = False,
    ) -> list[RetrievedChunk]:
        """dense_only=True skips sparse search and fusion/reranking
        entirely, returning the top_k dense hits directly in similarity
        order. Exists for side-by-side hybrid-vs-dense-only comparison
        (see the dashboard's comparison toggle), not for normal queries."""
        query_embedding = self.embedding_client.embed([query])[0]
        where = {"chunking_strategy": chunking_strategy} if chunking_strategy else None

        dense = self.vector_store.query(query_embedding, top_k=self.dense_top_k, where=where)

        if dense_only:
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

        sparse_pool = self.sparse_index.query(query, top_k=self.sparse_top_k * 5 if chunking_strategy else self.sparse_top_k)
        if chunking_strategy:
            sparse = [r for r in sparse_pool if r["metadata"].get("chunking_strategy") == chunking_strategy][: self.sparse_top_k]
        else:
            sparse = sparse_pool

        fusion_pool_size = max(self.rerank_candidate_pool, top_k) if self.reranker else top_k
        fused = reciprocal_rank_fusion(
            dense,
            sparse,
            k=self.rrf_k,
            top_k=fusion_pool_size,
            dense_weight=self.dense_weight,
            sparse_weight=self.sparse_weight,
        )

        if self.reranker is None:
            return fused[:top_k]
        return self.reranker.rerank(query, fused, top_k)
