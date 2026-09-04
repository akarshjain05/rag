"""End-to-end ingestion pipeline: load -> chunk -> embed -> dedup -> index.

One embedding API call per file (all of a file's chunks embedded in a single
batch request), then a sequential per-chunk dedup check against the vector
store's *current* contents — so a duplicate is caught whether it matches a
chunk from a previous run or one inserted earlier in this very call.
"""
from __future__ import annotations

from pathlib import Path

from rag_api.domain.chunking.chunking import chunk_document
from rag_api.adapters.storage.dedup import check_duplicate, check_duplicate_batch
from rag_api.adapters.vectorstore.embeddings import EmbeddingClient
from rag_api.adapters.storage.loaders import load_document
from rag_api.domain.models import ChunkingStrategy, IngestReport
from rag_api.adapters.vectorstore.sparse_index import BaseSparseIndex
from rag_api.adapters.vectorstore.vector_store import VectorStore


class IngestionPipeline:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_store: VectorStore,
        sparse_index: BaseSparseIndex,
        llm_client = None,
        image_store = None,
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
        self.llm_client = llm_client
        self.image_store = image_store
        self.image_store = None
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
    ) -> IngestReport:
        strategy = strategy or self.default_strategy
        source_name = Path(path).name

        try:
            doc = load_document(path, llm_client=self.llm_client, image_store=self.image_store)
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
            embedding_client=self.embedding_client if strategy in (ChunkingStrategy.SEMANTIC, ChunkingStrategy.STRUCTURE_AWARE) else None,
        )

        report = IngestReport(source_file=doc.source_file, chunking_strategy=strategy.value, chunks_created=len(chunks))
        if not chunks:
            return report

        embeddings = self.embedding_client.embed([c.text for c in chunks])

        inserted_ids = []
        inserted_texts = []
        inserted_metas = []
        inserted_embeddings = []
        
        # Batch dedup check
        dedups = check_duplicate_batch(embeddings, self.vector_store, threshold=self.dedup_similarity_threshold)
        
        for chunk, embedding, dedup in zip(chunks, embeddings, dedups):
            if dedup.is_duplicate:
                report.duplicates_skipped += 1
                report.duplicate_of.append(dedup.duplicate_of)
                continue
            inserted_ids.append(chunk.chunk_id)
            inserted_texts.append(chunk.text)
            inserted_metas.append(chunk.metadata())
            inserted_embeddings.append(embedding)
            report.chunks_inserted += 1
            
        if inserted_ids:
            self.vector_store.add_many(inserted_ids, inserted_embeddings, inserted_texts, inserted_metas)

        if inserted_ids:
            self.sparse_index.add_many(inserted_ids, inserted_texts, inserted_metas)

        return report

    def ingest_files(self, paths: list[str | Path], strategy: ChunkingStrategy | None = None) -> list[IngestReport]:
        return [self.ingest_file(p, strategy) for p in paths]
