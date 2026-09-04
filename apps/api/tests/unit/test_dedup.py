from __future__ import annotations

from rag_api.adapters.storage.dedup import check_duplicate


def test_empty_store_is_never_a_duplicate(vector_store):
    result = check_duplicate([1.0, 0.0, 0.0], vector_store, threshold=0.95)
    assert result.is_duplicate is False
    assert result.duplicate_of is None


def test_identical_embedding_is_flagged_as_duplicate(vector_store):
    vector_store.add("a", [1.0, 0.0, 0.0], "original chunk text", {"source_document": "x"})

    result = check_duplicate([1.0, 0.0, 0.0], vector_store, threshold=0.95)

    assert result.is_duplicate is True
    assert result.duplicate_of == "a"
    assert result.similarity > 0.95


def test_dissimilar_embedding_is_not_a_duplicate(vector_store):
    vector_store.add("a", [1.0, 0.0, 0.0], "original chunk text", {"source_document": "x"})

    result = check_duplicate([0.0, 1.0, 0.0], vector_store, threshold=0.95)

    assert result.is_duplicate is False


def test_threshold_boundary_is_respected(vector_store):
    vector_store.add("a", [1.0, 0.0], "text", {"source_document": "x"})
    # a vector at ~0.90 cosine similarity to [1,0]
    near = [0.90, (1 - 0.90 ** 2) ** 0.5]

    strict = check_duplicate(near, vector_store, threshold=0.95)
    lenient = check_duplicate(near, vector_store, threshold=0.5)

    assert strict.is_duplicate is False
    assert lenient.is_duplicate is True


def test_check_duplicate_within_same_batch(vector_store, fake_embedder):
    """Two near-identical chunks inserted back to back in the same batch
    should still be caught -- dedup checks against whatever is already in
    the store *right now*, including earlier insertions from this run."""
    text_a = "The vacation policy allows ten days of paid leave per year."
    text_b = "The vacation policy allows ten days of paid leave per year!"  # near-duplicate

    emb_a, emb_b = fake_embedder.embed([text_a, text_b])

    first = check_duplicate(emb_a, vector_store, threshold=0.9)
    assert first.is_duplicate is False
    vector_store.add("chunk_a", emb_a, text_a, {"source_document": "x"})

    second = check_duplicate(emb_b, vector_store, threshold=0.9)
    assert second.is_duplicate is True
    assert second.duplicate_of == "chunk_a"
