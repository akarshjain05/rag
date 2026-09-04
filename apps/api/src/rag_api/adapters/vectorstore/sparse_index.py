"""Sparse (keyword) index implementations.

Provides an incremental SQLite FTS5 backend and the legacy in-memory BM25Okapi backend.
"""
from __future__ import annotations

import json
import re
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-z0-9]+")

def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BaseSparseIndex(ABC):
    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def add_many(self, chunk_ids: list[str], texts: list[str], metadatas: list[dict]) -> None: ...

    @abstractmethod
    def delete_source_document(self, source_document: str) -> int: ...

    @abstractmethod
    def rebuild_from(self, rows: list[dict]) -> None: ...  # full resync, kept as a repair tool

    @abstractmethod
    def query(self, query_text: str, top_k: int = 10) -> list[dict]: ...

    def chunk_ids(self) -> list[str]:
        # Helper for tests, typically only implemented efficiently for in-memory or small scales
        return []


class SparseIndex(BaseSparseIndex):
    """In-memory BM25 index that requires a full rebuild on every modification."""
    def __init__(self) -> None:
        self._chunk_ids: list[str] = []
        self._texts: list[str] = []
        self._metadatas: list[dict] = []
        self._bm25: BM25Okapi | None = None

    def count(self) -> int:
        return len(self._chunk_ids)

    def chunk_ids(self) -> list[str]:
        return list(self._chunk_ids)
        
    def add_many(self, chunk_ids: list[str], texts: list[str], metadatas: list[dict]) -> None:
        self._chunk_ids.extend(chunk_ids)
        self._texts.extend(texts)
        self._metadatas.extend(metadatas)
        self._bm25 = BM25Okapi([tokenize(t) for t in self._texts]) if self._texts else None

    def delete_source_document(self, source_document: str) -> int:
        remaining = [
            (cid, t, m)
            for cid, t, m in zip(self._chunk_ids, self._texts, self._metadatas)
            if m.get("source_document") != source_document
        ]
        deleted_count = len(self._chunk_ids) - len(remaining)
        self._chunk_ids = [r[0] for r in remaining]
        self._texts = [r[1] for r in remaining]
        self._metadatas = [r[2] for r in remaining]
        self._bm25 = BM25Okapi([tokenize(t) for t in self._texts]) if self._texts else None
        return deleted_count

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


class SQLiteFTS5SparseIndex(BaseSparseIndex):
    def __init__(self, path: str | Path):
        self._conn = sqlite3.connect(str(path))
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5("
            "chunk_id UNINDEXED, text, metadata UNINDEXED, source_document UNINDEXED)"
        )

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]

    def add_many(self, chunk_ids: list[str], texts: list[str], metadatas: list[dict]) -> None:
        self._conn.executemany(
            "INSERT INTO chunks_fts(chunk_id, text, metadata, source_document) VALUES (?, ?, ?, ?)",
            [(cid, t, json.dumps(m), m.get("source_document")) for cid, t, m in zip(chunk_ids, texts, metadatas)],
        )
        self._conn.commit()

    def delete_source_document(self, source_document: str) -> int:
        cur = self._conn.execute("DELETE FROM chunks_fts WHERE source_document = ?", (source_document,))
        self._conn.commit()
        return cur.rowcount

    def rebuild_from(self, rows: list[dict]) -> None:
        self._conn.execute("DELETE FROM chunks_fts")
        self.add_many(
            [r["chunk_id"] for r in rows],
            [r["text"] for r in rows],
            [r["metadata"] for r in rows]
        )

    def query(self, query_text: str, top_k: int = 10) -> list[dict]:
        # FTS5 needs OR or implicit AND for match. We use implicit AND.
        # But wait, bm25 query needs valid FTS5 syntax, so escaping quotes is good.
        # Alternatively, rank_bm25 just does token overlap. FTS5 exact phrase uses quotes.
        # FTS5 MATCH 'term1 OR term2' is closest to rank_bm25 OR semantics?
        # Actually, rank_bm25 matches ANY term. FTS5 by default matches ALL terms if space separated!
        # To match rank_bm25 behaviour, we should split and join with OR.
        terms = tokenize(query_text)
        if not terms:
            return []
        match_query = " OR ".join(terms)
        
        try:
            rows = self._conn.execute(
                "SELECT chunk_id, text, metadata, bm25(chunks_fts) AS score FROM chunks_fts "
                "WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?",
                (match_query, top_k),
            ).fetchall()
        except Exception as e:
            print("EXCEPTION:", e)
            print(f'SQLITE ERROR: {e}')
            return []
            
        # bm25() in FTS5 returns negative values (lower = better)
        return [{"chunk_id": r[0], "text": r[1], "metadata": json.loads(r[2]), "score": -r[3]} for r in rows]
        
    def chunk_ids(self) -> list[str]:
        rows = self._conn.execute("SELECT chunk_id FROM chunks_fts").fetchall()
        return [r[0] for r in rows]

def build_sparse_index(provider: str, persist_dir: str | Path | None = None) -> BaseSparseIndex:
    if provider == "in_memory":
        return SparseIndex()
    elif provider == "sqlite_fts5":
        if not persist_dir:
            raise ValueError("sqlite_fts5 requires persist_dir")
        path = Path(persist_dir)
        path.mkdir(parents=True, exist_ok=True)
        return SQLiteFTS5SparseIndex(path / "sparse_index.db")
    raise ValueError(f"Unknown sparse index provider: {provider}")

