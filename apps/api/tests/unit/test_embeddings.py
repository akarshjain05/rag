from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import numpy as np
import pytest

from rag_api.adapters.vectorstore.embeddings import (
    DeterministicFakeEmbeddingClient,
    LocalEmbeddingClient,
    OpenAIEmbeddingClient,
    build_embedding_client,
    cosine_similarity,
)


def test_cosine_similarity_identical_vectors_is_one():
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector_is_zero_not_nan():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_fake_embedder_is_deterministic(fake_embedder):
    a = fake_embedder.embed(["hello world"])[0]
    b = fake_embedder.embed(["hello world"])[0]
    assert a == b


def test_fake_embedder_shared_vocabulary_is_more_similar_than_unrelated(fake_embedder):
    base = "the quarterly revenue report shows strong growth"
    similar = "the quarterly revenue report shows steady growth"
    unrelated = "spark plugs need replacing during scheduled maintenance"

    vecs = fake_embedder.embed([base, similar, unrelated])
    sim_related = cosine_similarity(vecs[0], vecs[1])
    sim_unrelated = cosine_similarity(vecs[0], vecs[2])

    assert sim_related > sim_unrelated


def test_fake_embedder_vectors_are_unit_norm(fake_embedder):
    vec = fake_embedder.embed(["some arbitrary text"])[0]
    assert np.linalg.norm(vec) == pytest.approx(1.0, abs=1e-6)


def test_fake_embedder_empty_list_returns_empty():
    assert DeterministicFakeEmbeddingClient().embed([]) == []


def test_build_embedding_client_openai_requires_api_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_embedding_client("openai", openai_api_key=None)


def test_build_embedding_client_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        build_embedding_client("not-a-real-provider")


def test_openai_embedding_client_calls_sdk_correctly(monkeypatch):
    fake_response = MagicMock()
    fake_response.data = [MagicMock(embedding=[0.1, 0.2]), MagicMock(embedding=[0.3, 0.4])]
    fake_openai_instance = MagicMock()
    fake_openai_instance.embeddings.create.return_value = fake_response

    monkeypatch.setattr("openai.OpenAI", lambda api_key, base_url=None: fake_openai_instance)

    client = OpenAIEmbeddingClient(model="text-embedding-3-small", api_key="sk-test")
    result = client.embed(["a", "b"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    assert client.dimension == 1536
    fake_openai_instance.embeddings.create.assert_called_once_with(model="text-embedding-3-small", input=["a", "b"])


def test_local_embedding_client_wraps_sentence_transformers(monkeypatch):
    """sentence-transformers (and torch) are a large optional dependency not
    installed in this environment; the wrapper's own logic — calling
    .encode() correctly and exposing .dimension — is verified by injecting
    fake modules rather than skipping the test."""
    fake_st_model = MagicMock()
    fake_st_model.get_sentence_embedding_dimension.return_value = 384
    fake_st_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])

    fake_st_module = types.ModuleType("sentence_transformers")
    fake_st_module.SentenceTransformer = MagicMock(return_value=fake_st_model)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_module)

    # LocalEmbeddingClient also imports transformers and torch
    fake_auto_model = MagicMock()
    fake_auto_model.config.hidden_size = 384
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoModel = MagicMock()
    fake_transformers.AutoModel.from_pretrained = MagicMock(return_value=fake_auto_model)
    fake_transformers.AutoTokenizer = MagicMock()
    fake_transformers.AutoTokenizer.from_pretrained = MagicMock(return_value=MagicMock())
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    fake_torch = types.ModuleType("torch")
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    client = LocalEmbeddingClient(model_name="fake/model")
    result = client.embed(["hello"])

    assert result == [[0.1, 0.2, 0.3]]
    assert client.dimension == 384
    fake_st_model.encode.assert_called_once_with(["hello"], normalize_embeddings=True, show_progress_bar=False)


def test_local_embedding_client_empty_list_returns_empty(monkeypatch):
    fake_st_model = MagicMock()
    fake_st_model.get_sentence_embedding_dimension.return_value = 384
    fake_st_module = types.ModuleType("sentence_transformers")
    fake_st_module.SentenceTransformer = MagicMock(return_value=fake_st_model)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_module)

    fake_auto_model = MagicMock()
    fake_auto_model.config.hidden_size = 384
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoModel = MagicMock()
    fake_transformers.AutoModel.from_pretrained = MagicMock(return_value=fake_auto_model)
    fake_transformers.AutoTokenizer = MagicMock()
    fake_transformers.AutoTokenizer.from_pretrained = MagicMock(return_value=MagicMock())
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    fake_torch = types.ModuleType("torch")
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    client = LocalEmbeddingClient(model_name="fake/model")
    assert client.embed([]) == []
    fake_st_model.encode.assert_not_called()
