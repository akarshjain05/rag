"""Embedding client abstraction.

Three implementations behind one interface so the rest of the pipeline never
branches on provider:

- OpenAIEmbeddingClient   -> text-embedding-3-small, paid, needs OPENAI_API_KEY
- LocalEmbeddingClient    -> sentence-transformers, free, CPU, no API key
- DeterministicFakeEmbeddingClient -> hash-based bag-of-words vectors, used
  in tests so similarity-dependent logic (dedup, semantic chunking) is
  exercised without any network access: texts sharing more words land
  closer together in cosine space, same as a real embedder would tend to,
  which is enough to make similarity-threshold logic meaningfully testable.
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import numpy as np


class EmbeddingClient(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, same order."""

    @property
    @abstractmethod
    def dimension(self) -> int: ...


class OpenAIEmbeddingClient(EmbeddingClient):
    _DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, model: str = "text-embedding-3-small", api_key: str | None = None, base_url: str | None = None):
        from openai import OpenAI  # local import: don't require the SDK unless used

        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for EMBEDDING_PROVIDER=openai")
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._dimension = self._DIMENSIONS.get(model, 1536)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in resp.data]

    @property
    def dimension(self) -> int:
        return self._dimension


class LocalEmbeddingClient(EmbeddingClient):
    """Free, local, CPU-only embeddings via sentence-transformers.

    Import of `sentence_transformers` is lazy and only happens here, so
    installing it (and its torch dependency) is optional and only required
    when EMBEDDING_PROVIDER=local is actually selected.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised via mocked test instead
            raise ImportError(
                "EMBEDDING_PROVIDER=local requires sentence-transformers. "
                "Install with: pip install -r requirements-local.txt"
            ) from exc

        self._model = SentenceTransformer(model_name)
        self._dimension = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    @property
    def dimension(self) -> int:
        return self._dimension


_FAKE_EMBEDDING_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "and", "or", "of", "to",
    "in", "on", "for", "with", "at", "by", "it", "this", "that", "as", "be",
}


class DeterministicFakeEmbeddingClient(EmbeddingClient):
    """Test-only. Deterministic, hash-based bag-of-words embeddings —
    no network, no model download, no API key. Texts with more shared
    (non-stopword) vocabulary land closer together in cosine similarity,
    same directional behaviour a real embedder has, which is what makes
    similarity-threshold logic (dedup, semantic chunking) testable without
    a real model."""

    def __init__(self, dimension: int = 128):
        self._dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = np.zeros(self._dimension, dtype=np.float64)
        words = [w for w in text.lower().split() if w.isalnum() and w not in _FAKE_EMBEDDING_STOPWORDS]
        for w in words:
            digest = hashlib.md5(w.encode("utf-8")).hexdigest()
            idx = int(digest, 16) % self._dimension
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        else:
            vec[0] = 1.0  # empty string -> arbitrary unit vector, avoids NaNs
        return vec.tolist()

    @property
    def dimension(self) -> int:
        return self._dimension


def build_embedding_client(
    provider: str,
    *,
    openai_model: str = "text-embedding-3-small",
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    local_model: str = "sentence-transformers/all-MiniLM-L6-v2",
) -> EmbeddingClient:
    if provider == "openai":
        return OpenAIEmbeddingClient(model=openai_model, api_key=openai_api_key, base_url=openai_base_url)
    if provider == "local":
        return LocalEmbeddingClient(model_name=local_model)
    raise ValueError(f"Unknown embedding provider: {provider!r} (expected 'openai' or 'local')")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
