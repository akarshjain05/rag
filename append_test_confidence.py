with open("apps/api/tests/unit/test_confidence.py", "a") as f:
    f.write("""

def make_chunk_full(dense_similarity=None, rerank_score=None):
    from rag_api.domain.models import RetrievedChunk
    return RetrievedChunk(chunk_id="x", text="t", metadata={}, dense_similarity=dense_similarity, rerank_score=rerank_score)

def test_retrieval_confidence_blends_rerank_and_dense_when_reranker_active():
    import pytest
    chunks = [make_chunk_full(dense_similarity=0.85, rerank_score=0.0)]
    result = compute_retrieval_confidence(chunks)
    assert result > 0.0
    assert result == pytest.approx(0.3 * 0.85, abs=1e-4)

def test_retrieval_confidence_still_low_when_both_signals_agree_its_bad():
    chunks = [make_chunk_full(dense_similarity=0.05, rerank_score=0.0)]
    assert compute_retrieval_confidence(chunks) < 0.3
""")
