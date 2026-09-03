"""BM25 sparse (keyword) index.

`rank_bm25.BM25Okapi` has no incremental-update or persistence API — every
insert requires rebuilding the ranker over the full tokenized corpus. Rather
than inventing a second on-disk persistence format that could drift out of
sync with ChromaDB, this index treats the vector store as the single source
of truth: `rebuild_from()` reconstructs the whole in-memory BM25 index from
whatever is currently in Chroma. Call it once at startup and again after any
write, so "both indexes stay in sync" by construction rather than by
discipline. For corpora large enough that a full rebuild per write becomes
too slow, the fix is a proper incremental text index (e.g. Tantivy,
Elasticsearch) — noted here rather than silently pretending rank_bm25 scales
to that.
"""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class SparseIndex:
    def __init__(self) -> None:
        self._chunk_ids: list[str] = []
        self._texts: list[str] = []
        self._metadatas: list[dict] = []
        self._bm25: BM25Okapi | None = None

    def count(self) -> int:
        return len(self._chunk_ids)

    def chunk_ids(self) -> list[str]:
        return list(self._chunk_ids)

    def rebuild_from(self, rows: list[dict]) -> None:
        """rows: [{chunk_id, text, metadata}, ...] — the same shape
        VectorStore.get_all()/add() use, so the two can be kept in lockstep
        without a translation layer."""
        self._chunk_ids = [r["chunk_id"] for r in rows]
        self._texts = [r["text"] for r in rows]
        self._metadatas = [r["metadata"] for r in rows]
        self._bm25 = BM25Okapi([tokenize(t) for t in self._texts]) if self._texts else None

    def query(self, query_text: str, top_k: int = 10) -> list[dict]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(query_text))
        ranked = sorted(
            ((i, s) for i, s in enumerate(scores) if s > 0),
            key=lambda pair: pair[1],
            reverse=True,
        )[:top_k]
        return [
            {
                "chunk_id": self._chunk_ids[i],
                "text": self._texts[i],
                "metadata": self._metadatas[i],
                "score": float(s),
            }
            for i, s in ranked
        ]
