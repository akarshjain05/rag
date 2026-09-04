"""Thin wrapper around a ChromaDB collection.

Embeddings are always supplied explicitly by the caller (via an
`EmbeddingClient`) rather than using Chroma's built-in embedding functions —
that keeps provider choice (OpenAI vs local) in one place (`app/embeddings.py`)
instead of split across two configuration surfaces.

Two modes, same interface (Chroma's `Collection` API is identical for both
client types, so nothing below branches on mode):
- "embedded" (default): `PersistentClient` writing to a local directory --
  simplest path for local dev, no extra process to run.
- "http": `HttpClient` against a separate Chroma server -- used in
  docker-compose, where Chroma runs as its own service so storage isn't
  tied to the API container's lifecycle.
"""
from __future__ import annotations

from pathlib import Path

import chromadb


class VectorStore:
    def __init__(
        self,
        persist_dir: str | Path | None = None,
        collection_name: str = "internal_docs",
        *,
        mode: str = "embedded",
        host: str = "chromadb",
        port: int = 8000,
    ):
        if mode == "http":
            self._client = chromadb.HttpClient(host=host, port=port)
        elif mode == "embedded":
            if persist_dir is None:
                raise ValueError("persist_dir is required when mode='embedded'")
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(persist_dir))
        else:
            raise ValueError(f"Unknown VectorStore mode: {mode!r} (expected 'embedded' or 'http')")

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return self._collection.count()

    def add(self, chunk_id: str, embedding: list[float], text: str, metadata: dict) -> None:
        self._collection.add(ids=[chunk_id], embeddings=[embedding], documents=[text], metadatas=[metadata])

    def add_many(self, chunk_ids: list[str], embeddings: list[list[float]], texts: list[str], metadatas: list[dict]) -> None:
        if not chunk_ids:
            return
        self._collection.add(ids=chunk_ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

    def nearest(self, embedding: list[float], top_k: int = 1) -> list[dict]:
        """Nearest neighbours to `embedding`. Returns a list (possibly empty
        if the collection has no vectors yet) of
        {chunk_id, text, metadata, similarity}, ordered nearest-first.
        `similarity` = 1 - cosine distance (the collection is configured
        with hnsw:space=cosine)."""
        if self.count() == 0:
            return []
        n = min(top_k, self.count())
        res = self._collection.query(query_embeddings=[embedding], n_results=n)
        out = []
        ids = res["ids"][0]
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        dists = res["distances"][0]
        for cid, doc, meta, dist in zip(ids, docs, metas, dists):
            out.append({"chunk_id": cid, "text": doc, "metadata": meta, "similarity": 1.0 - dist})
        return out

    def query(self, embedding: list[float], top_k: int = 10, where: dict | None = None) -> list[dict]:
        """Dense search for retrieval. Same shape as `nearest`."""
        if self.count() == 0:
            return []
        n = min(top_k, self.count())
        res = self._collection.query(query_embeddings=[embedding], n_results=n, where=where)
        out = []
        for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
            out.append({"chunk_id": cid, "text": doc, "metadata": meta, "similarity": 1.0 - dist})
        return out

    def get_all(self) -> list[dict]:
        if self.count() == 0:
            return []
        res = self._collection.get()
        out = []
        for cid, doc, meta in zip(res["ids"], res["documents"], res["metadatas"]):
            out.append({"chunk_id": cid, "text": doc, "metadata": meta})
        return out

    def list_source_documents(self) -> list[str]:
        seen: dict[str, None] = {}
        for row in self.get_all():
            seen.setdefault(row["metadata"].get("source_document", "unknown"), None)
        return list(seen.keys())

    def delete_source_document(self, source_document: str) -> int:
        matches = self._collection.get(where={"source_document": source_document})
        ids = matches["ids"]
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)
