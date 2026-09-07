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


def check_duplicate_batch(embeddings: list[list[float]], store: VectorStore, threshold: float = 0.95, exclude_source_document: str | None = None) -> list[DedupResult]:
    try:
        batch_res = store.nearest_batch(embeddings, top_k=1, exclude_source_document=exclude_source_document)
    except AttributeError:
        # Fallback if vector store doesn't have nearest_batch
        return [check_duplicate(emb, store, threshold, exclude_source_document=exclude_source_document) for emb in embeddings]
        
    results = []
    for res in batch_res:
        if not res:
            results.append(DedupResult(is_duplicate=False))
        elif res[0]["similarity"] >= threshold:
            results.append(DedupResult(is_duplicate=True, duplicate_of=res[0]["chunk_id"]))
        else:
            results.append(DedupResult(is_duplicate=False))
    return results

def check_duplicate(embedding: list[float], store: VectorStore, threshold: float = 0.95, exclude_source_document: str | None = None) -> DedupResult:
    neighbors = store.nearest(embedding, top_k=1, exclude_source_document=exclude_source_document)
    if not neighbors:
        return DedupResult(is_duplicate=False)
    best = neighbors[0]
    if best["similarity"] > threshold:
        return DedupResult(is_duplicate=True, duplicate_of=best["chunk_id"], similarity=best["similarity"])
    return DedupResult(is_duplicate=False, similarity=best["similarity"])
