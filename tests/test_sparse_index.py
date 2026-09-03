from __future__ import annotations

from app.sparse_index import SparseIndex, tokenize


def test_tokenize_lowercases_and_strips_punctuation():
    assert tokenize("Hello, World! Vacation-policy?") == ["hello", "world", "vacation", "policy"]


def test_empty_index_returns_no_results(sparse_index):
    assert sparse_index.count() == 0
    assert sparse_index.query("anything") == []


def test_rebuild_from_and_keyword_query_ranks_exact_term_match_first(sparse_index):
    rows = [
        {"chunk_id": "a", "text": "vacation policy allows ten days per year", "metadata": {}},
        {"chunk_id": "b", "text": "remote work requires manager approval", "metadata": {}},
        {"chunk_id": "c", "text": "vacation requests go through the HR portal", "metadata": {}},
    ]
    sparse_index.rebuild_from(rows)
    assert sparse_index.count() == 3

    results = sparse_index.query("vacation policy", top_k=3)
    result_ids = [r["chunk_id"] for r in results]

    assert "a" in result_ids
    assert result_ids[0] == "a"  # contains both query terms -> highest BM25 score
    assert "b" not in result_ids  # zero term overlap -> excluded, not just ranked last


def test_query_top_k_limits_results(sparse_index):
    # BM25's classic IDF goes non-positive for a term appearing in most/all
    # of the corpus, so matches need to stay a minority against unrelated
    # "noise" docs for their score to be positive and not get filtered out.
    matching = [{"chunk_id": f"match_{i}", "text": "shared keyword appears in this document", "metadata": {}} for i in range(5)]
    noise = [{"chunk_id": f"noise_{i}", "text": f"completely unrelated content about topic {i}", "metadata": {}} for i in range(15)]
    sparse_index.rebuild_from(matching + noise)

    results = sparse_index.query("shared keyword", top_k=3)

    assert len(results) == 3
    assert all(r["chunk_id"].startswith("match_") for r in results)


def test_rebuild_from_replaces_previous_contents(sparse_index):
    sparse_index.rebuild_from([{"chunk_id": "old", "text": "old content", "metadata": {}}])
    assert sparse_index.count() == 1

    sparse_index.rebuild_from([{"chunk_id": "new1", "text": "new content one", "metadata": {}},
                                {"chunk_id": "new2", "text": "new content two", "metadata": {}}])
    assert sparse_index.count() == 2
    results = sparse_index.query("old content")
    assert results == []


def test_rebuild_from_empty_rows_clears_index(sparse_index):
    sparse_index.rebuild_from([{"chunk_id": "a", "text": "something", "metadata": {}}])
    sparse_index.rebuild_from([])
    assert sparse_index.count() == 0
    assert sparse_index.query("something") == []
