"""End-to-end ingestion pipeline: load -> chunk -> embed -> dedup -> index.

One embedding API call per file (all of a file's chunks embedded in a single
batch request), then a sequential per-chunk dedup check against the vector
store's *current* contents — so a duplicate is caught whether it matches a
chunk from a previous run or one inserted earlier in this very call.
"""
from __future__ import annotations

from pathlib import Path

from app.chunking import chunk_document
from app.dedup import check_duplicate
from app.embeddings import EmbeddingClient
from app.loaders import load_document
from app.models import ChunkingStrategy, IngestReport
from app.sparse_index import SparseIndex
from app.vector_store import VectorStore


class IngestionPipeline:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_store: VectorStore,
        sparse_index: SparseIndex,
        *,
        default_strategy: ChunkingStrategy = ChunkingStrategy.STRUCTURE_AWARE,
        fixed_chunk_size: int = 1000,
        fixed_chunk_overlap: int = 150,
        structure_max_section_size: int = 1200,
        semantic_similarity_threshold: float = 0.55,
        semantic_max_chunk_chars: int = 1500,
        semantic_min_chunk_chars: int = 200,
        dedup_similarity_threshold: float = 0.95,
    ):
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.sparse_index = sparse_index
        self.default_strategy = default_strategy
        self.fixed_chunk_size = fixed_chunk_size
        self.fixed_chunk_overlap = fixed_chunk_overlap
        self.structure_max_section_size = structure_max_section_size
        self.semantic_similarity_threshold = semantic_similarity_threshold
        self.semantic_max_chunk_chars = semantic_max_chunk_chars
        self.semantic_min_chunk_chars = semantic_min_chunk_chars
        self.dedup_similarity_threshold = dedup_similarity_threshold

    def ingest_file(
        self,
        path: str | Path,
        strategy: ChunkingStrategy | None = None,
        *,
        sync_sparse_index: bool = True,
    ) -> IngestReport:
        strategy = strategy or self.default_strategy
        source_name = Path(path).name

        try:
            doc = load_document(path)
        except Exception as exc:  # noqa: BLE001 - reported, not raised, so batches survive one bad file
            return IngestReport(source_file=source_name, chunking_strategy=strategy.value, error=str(exc))

        chunks = chunk_document(
            doc,
            strategy,
            fixed_chunk_size=self.fixed_chunk_size,
            fixed_chunk_overlap=self.fixed_chunk_overlap,
            structure_max_section_size=self.structure_max_section_size,
            semantic_similarity_threshold=self.semantic_similarity_threshold,
            semantic_max_chunk_chars=self.semantic_max_chunk_chars,
            semantic_min_chunk_chars=self.semantic_min_chunk_chars,
            embedding_client=self.embedding_client if strategy == ChunkingStrategy.SEMANTIC else None,
        )

        report = IngestReport(source_file=doc.source_file, chunking_strategy=strategy.value, chunks_created=len(chunks))
        if not chunks:
            return report

        embeddings = self.embedding_client.embed([c.text for c in chunks])

        for chunk, embedding in zip(chunks, embeddings):
            dedup = check_duplicate(embedding, self.vector_store, threshold=self.dedup_similarity_threshold)
            if dedup.is_duplicate:
                report.duplicates_skipped += 1
                report.duplicate_of.append(dedup.duplicate_of)
                continue
            self.vector_store.add(chunk.chunk_id, embedding, chunk.text, chunk.metadata())
            report.chunks_inserted += 1

        if sync_sparse_index:
            self.sparse_index.rebuild_from(self.vector_store.get_all())

        return report

    def ingest_files(self, paths: list[str | Path], strategy: ChunkingStrategy | None = None) -> list[IngestReport]:
        reports = [self.ingest_file(p, strategy, sync_sparse_index=False) for p in paths]
        self.sparse_index.rebuild_from(self.vector_store.get_all())
        return reports
