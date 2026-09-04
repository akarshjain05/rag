"""Near-duplicate detection.

Checked one chunk at a time, immediately before insertion, against whatever
is already in the vector store — which includes chunks inserted earlier in
the *same* ingestion batch, not just prior runs. That catches duplicate
content within one document (e.g. a repeated boilerplate section) as well
as duplicates across documents.
"""
from __future__ import annotations

from dataclasses import dataclass

from rag_api.adapters.vectorstore.vector_store import VectorStore


@dataclass
class DedupResult:
    is_duplicate: bool
    duplicate_of: str | None = None
    similarity: float | None = None


def check_duplicate(embedding: list[float], store: VectorStore, threshold: float = 0.95) -> DedupResult:
    neighbors = store.nearest(embedding, top_k=1)
    if not neighbors:
        return DedupResult(is_duplicate=False)
    best = neighbors[0]
    if best["similarity"] > threshold:
        return DedupResult(is_duplicate=True, duplicate_of=best["chunk_id"], similarity=best["similarity"])
    return DedupResult(is_duplicate=False, similarity=best["similarity"])
