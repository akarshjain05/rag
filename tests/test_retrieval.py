from __future__ import annotations

import pytest

from app.retrieval import HybridRetriever, reciprocal_rank_fusion


def _result(chunk_id, text="text", metadata=None):
    return {"chunk_id": chunk_id, "text": text, "metadata": metadata or {}}


# --------------------------------------------------------------------------
# reciprocal_rank_fusion (pure function, no I/O)
# --------------------------------------------------------------------------
def test_rrf_boosts_docs_ranked_in_both_lists():
    dense = [_result("shared"), _result("dense_only")]
    sparse = [_result("sparse_only"), _result("shared")]

    fused = reciprocal_rank_fusion(dense, sparse, k=60, top_k=3)
    fused_ids = [c.chunk_id for c in fused]

    assert fused_ids[0] == "shared"  # appears in both -> highest combined score
    assert set(fused_ids) == {"shared", "dense_only", "sparse_only"}


def test_rrf_tracks_dense_and_sparse_rank_provenance():
    dense = [_result("a"), _result("b")]
    sparse = [_result("b"), _result("a")]

    fused = {c.chunk_id: c for c in reciprocal_rank_fusion(dense, sparse, top_k=2)}

    assert fused["a"].dense_rank == 1
    assert fused["a"].sparse_rank == 2
    assert fused["b"].dense_rank == 2
    assert fused["b"].sparse_rank == 1


def test_rrf_respects_top_k():
    dense = [_result(str(i)) for i in range(10)]
    fused = reciprocal_rank_fusion(dense, [], top_k=3)
    assert len(fused) == 3


def test_rrf_handles_one_empty_list():
    dense = [_result("a"), _result("b")]
    fused = reciprocal_rank_fusion(dense, [], top_k=5)
    assert [c.chunk_id for c in fused] == ["a", "b"]
    assert all(c.sparse_rank is None for c in fused)


def test_rrf_both_empty_returns_empty():
    assert reciprocal_rank_fusion([], [], top_k=5) == []


def test_rrf_populates_dense_similarity_only_for_dense_hits():
    dense = [{"chunk_id": "a", "text": "t", "metadata": {}, "similarity": 0.87}]
    sparse = [{"chunk_id": "b", "text": "t", "metadata": {}, "score": 4.2}]

    fused = {c.chunk_id: c for c in reciprocal_rank_fusion(dense, sparse, top_k=2)}

    assert fused["a"].dense_similarity == 0.87
    assert fused["b"].dense_similarity is None  # sparse-only hit -- no dense signal to report


def test_rrf_dense_similarity_prefers_dense_dict_when_hit_in_both_lists():
    # same chunk_id in both lists: the dense result (with "similarity") is
    # the one stored first, so dense_similarity should still be populated
    dense = [{"chunk_id": "shared", "text": "t", "metadata": {}, "similarity": 0.6}]
    sparse = [{"chunk_id": "shared", "text": "t", "metadata": {}, "score": 3.0}]

    fused = reciprocal_rank_fusion(dense, sparse, top_k=1)

    assert fused[0].dense_similarity == 0.6


def test_rrf_default_weights_are_equivalent_to_unweighted():
    dense = [_result("a"), _result("b")]
    sparse = [_result("b"), _result("a")]
    default = reciprocal_rank_fusion(dense, sparse, top_k=2)
    explicit_equal = reciprocal_rank_fusion(dense, sparse, top_k=2, dense_weight=1.0, sparse_weight=1.0)
    assert [c.fused_score for c in default] == [c.fused_score for c in explicit_equal]


def test_rrf_weighting_changes_which_doc_ranks_first():
    # symmetric setup: each doc is rank-1 in one list, rank-3 in the other
    dense = [_result("dense_favorite"), _result("other"), _result("sparse_favorite")]
    sparse = [_result("sparse_favorite"), _result("other"), _result("dense_favorite")]

    equal = reciprocal_rank_fusion(dense, sparse, top_k=3, dense_weight=1.0, sparse_weight=1.0)
    scores = {c.chunk_id: c.fused_score for c in equal}
    assert scores["dense_favorite"] == pytest.approx(scores["sparse_favorite"])  # symmetric -> exact tie

    dense_heavy = reciprocal_rank_fusion(dense, sparse, top_k=1, dense_weight=10.0, sparse_weight=0.1)
    assert dense_heavy[0].chunk_id == "dense_favorite"

    sparse_heavy = reciprocal_rank_fusion(dense, sparse, top_k=1, dense_weight=0.1, sparse_weight=10.0)
    assert sparse_heavy[0].chunk_id == "sparse_favorite"


# --------------------------------------------------------------------------
# HybridRetriever (integration with real VectorStore + SparseIndex)
# --------------------------------------------------------------------------
def _index_chunk(vector_store, sparse_index_rows, fake_embedder, chunk_id, text, metadata):
    embedding = fake_embedder.embed([text])[0]
    vector_store.add(chunk_id, embedding, text, metadata)
    sparse_index_rows.append({"chunk_id": chunk_id, "text": text, "metadata": metadata})


def test_hybrid_retriever_finds_relevant_chunk_by_keyword_and_meaning(fake_embedder, vector_store, sparse_index):
    rows = []
    _index_chunk(vector_store, rows, fake_embedder, "vacation", "employees accrue vacation days each month", {"source_document": "handbook.md", "chunking_strategy": "structure_aware", "section_heading": "", "page_number": -1})
    _index_chunk(vector_store, rows, fake_embedder, "remote", "remote work requires manager approval", {"source_document": "handbook.md", "chunking_strategy": "structure_aware", "section_heading": "", "page_number": -1})
    sparse_index.rebuild_from(rows)

    retriever = HybridRetriever(fake_embedder, vector_store, sparse_index, dense_top_k=5, sparse_top_k=5)
    results = retriever.retrieve("how many vacation days do employees accrue", top_k=2)

    assert results
    assert results[0].chunk_id == "vacation"


def test_hybrid_retriever_chunking_strategy_filter(fake_embedder, vector_store, sparse_index):
    rows = []
    _index_chunk(vector_store, rows, fake_embedder, "fixed_chunk", "vacation policy details here", {"source_document": "h.md", "chunking_strategy": "fixed_size", "section_heading": "", "page_number": -1})
    _index_chunk(vector_store, rows, fake_embedder, "semantic_chunk", "vacation policy details here", {"source_document": "h.md", "chunking_strategy": "semantic", "section_heading": "", "page_number": -1})
    sparse_index.rebuild_from(rows)

    retriever = HybridRetriever(fake_embedder, vector_store, sparse_index)
    results = retriever.retrieve("vacation policy", top_k=5, chunking_strategy="semantic")

    assert len(results) == 1
    assert results[0].chunk_id == "semantic_chunk"


def test_hybrid_retriever_empty_index_returns_empty(fake_embedder, vector_store, sparse_index):
    retriever = HybridRetriever(fake_embedder, vector_store, sparse_index)
    assert retriever.retrieve("anything", top_k=5) == []


def test_dense_only_skips_sparse_and_fusion_entirely(fake_embedder, vector_store, sparse_index):
    rows = []
    _index_chunk(vector_store, rows, fake_embedder, "a", "vacation policy accrual details", {"source_document": "h.md"})
    _index_chunk(vector_store, rows, fake_embedder, "b", "remote work approval details", {"source_document": "h.md"})
    sparse_index.rebuild_from(rows)

    retriever = HybridRetriever(fake_embedder, vector_store, sparse_index, dense_top_k=5, sparse_top_k=5)
    results = retriever.retrieve("vacation policy", top_k=2, dense_only=True)

    assert len(results) == 2
    assert all(r.sparse_rank is None for r in results)  # sparse never consulted
    assert all(r.dense_similarity is not None for r in results)
    assert results[0].dense_rank == 1
    assert results[1].dense_rank == 2


def test_dense_only_bypasses_the_reranker(fake_embedder, vector_store, sparse_index):
    rows = []
    for i in range(5):
        _index_chunk(vector_store, rows, fake_embedder, f"c{i}", f"content number {i}", {"source_document": "h.md"})
    sparse_index.rebuild_from(rows)

    fake_reranker = _FakeReranker()
    retriever = HybridRetriever(fake_embedder, vector_store, sparse_index, reranker=fake_reranker)

    retriever.retrieve("content", top_k=3, dense_only=True)

    assert fake_reranker.received_pool_size is None  # never called


def test_dense_only_respects_chunking_strategy_filter(fake_embedder, vector_store, sparse_index):
    rows = []
    _index_chunk(vector_store, rows, fake_embedder, "fixed_chunk", "vacation policy", {"source_document": "h.md", "chunking_strategy": "fixed_size"})
    _index_chunk(vector_store, rows, fake_embedder, "semantic_chunk", "vacation policy", {"source_document": "h.md", "chunking_strategy": "semantic"})
    sparse_index.rebuild_from(rows)

    retriever = HybridRetriever(fake_embedder, vector_store, sparse_index)
    results = retriever.retrieve("vacation policy", top_k=5, chunking_strategy="semantic", dense_only=True)

    assert len(results) == 1
    assert results[0].chunk_id == "semantic_chunk"


def test_hybrid_retrieval_falls_back_gracefully_when_sparse_finds_nothing(fake_embedder, vector_store, sparse_index):
    """With a corpus this small, a query term appearing in exactly one of
    two documents can land BM25's classic IDF at ~0, so sparse legitimately
    returns zero candidates (verified directly against rank_bm25, not
    assumed). Hybrid retrieval should still work off dense search alone
    rather than returning nothing just because one signal was empty."""
    query = "how many vacation days per month"
    doc_a = "Employees accrue paid days off at a fixed rate every month"  # correct, weak keyword overlap
    doc_b = "Vacation requests must be submitted two weeks in advance through the HR portal"  # wrong, strong keyword overlap

    rows = []
    _index_chunk(vector_store, rows, fake_embedder, "a", doc_a, {"source_document": "a.md"})
    _index_chunk(vector_store, rows, fake_embedder, "b", doc_b, {"source_document": "b.md"})
    sparse_index.rebuild_from(rows)
    assert sparse_index.query(query) == []  # confirms the degenerate-BM25-score premise holds here

    retriever = HybridRetriever(fake_embedder, vector_store, sparse_index)
    results = retriever.retrieve(query, top_k=2)

    assert len(results) == 2
    assert results[0].chunk_id == "a"  # dense ranking alone still surfaces the right doc first
    assert all(r.sparse_rank is None for r in results)


# --------------------------------------------------------------------------
# Reranking integration
# --------------------------------------------------------------------------
class _FakeReranker:
    """Test double: reverses the fused pool and stamps a score, so tests can
    tell the reranker's output made it through untouched, and records how
    large a pool it was actually given."""

    def __init__(self):
        self.received_pool_size = None

    def rerank(self, query, candidates, top_k):
        self.received_pool_size = len(candidates)
        reordered = list(reversed(candidates))
        for i, c in enumerate(reordered):
            c.rerank_score = float(i)
        return reordered[:top_k]


def test_hybrid_retriever_with_reranker_fuses_to_the_larger_candidate_pool(fake_embedder, vector_store, sparse_index):
    rows = []
    for i in range(15):
        _index_chunk(vector_store, rows, fake_embedder, f"chunk_{i}", f"vacation policy detail number {i}", {"source_document": "h.md"})
    sparse_index.rebuild_from(rows)

    fake_reranker = _FakeReranker()
    retriever = HybridRetriever(
        fake_embedder, vector_store, sparse_index,
        dense_top_k=15, sparse_top_k=15,
        reranker=fake_reranker, rerank_candidate_pool=12,
    )

    results = retriever.retrieve("vacation policy", top_k=3)

    assert fake_reranker.received_pool_size == 12  # fused to the pool size, not straight to top_k=3
    assert len(results) == 3
    assert all(r.rerank_score is not None for r in results)  # reranker's output, not raw fusion


def test_hybrid_retriever_without_reranker_fuses_straight_to_top_k(fake_embedder, vector_store, sparse_index):
    rows = []
    for i in range(15):
        _index_chunk(vector_store, rows, fake_embedder, f"chunk_{i}", f"vacation policy detail number {i}", {"source_document": "h.md"})
    sparse_index.rebuild_from(rows)

    retriever = HybridRetriever(fake_embedder, vector_store, sparse_index, dense_top_k=15, sparse_top_k=15)
    results = retriever.retrieve("vacation policy", top_k=3)

    assert len(results) == 3
    assert all(r.rerank_score is None for r in results)
