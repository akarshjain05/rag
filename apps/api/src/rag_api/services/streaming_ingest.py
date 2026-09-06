from __future__ import annotations
from pathlib import Path
from typing import Callable, Iterator

from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag_api.adapters.storage.dedup import check_duplicate_batch
from rag_api.adapters.vectorstore.embeddings import EmbeddingClient
from rag_api.adapters.vectorstore.vector_store import VectorStore
from rag_api.domain.models import Chunk, ChunkingStrategy, IngestReport


def stream_text_chunks(
    path: Path,
    splitter: RecursiveCharacterTextSplitter,
    *,
    read_block_chars: int = 200_000,
    tail_overlap_chars: int = 2_000,
) -> Iterator[str]:
    """Reads a large text/markdown file in bounded blocks. Carries the last
    `tail_overlap_chars` of each block forward uncommitted, so a paragraph
    or sentence straddling a read boundary is never split mid-unit -- the
    bug in the naive byte-buffer version."""
    tail = ""
    with path.open("r", encoding="utf-8", errors="replace") as f:
        while True:
            block = f.read(read_block_chars)
            if not block:
                break
            text = tail + block
            split_at = max(0, len(text) - tail_overlap_chars)
            safe_text, tail = text[:split_at], text[split_at:]
            for chunk in splitter.split_text(safe_text):
                yield chunk
    if tail.strip():
        yield from splitter.split_text(tail)


def embed_and_index_stream(
    chunk_texts: Iterator[str],
    *,
    source_document: str,
    embedding_client: EmbeddingClient,
    vector_store: VectorStore,
    dedup_threshold: float,
    batch_size: int = 64,
    progress_cb: Callable[[int], None] | None = None,
) -> IngestReport:
    report = IngestReport(source_file=source_document, chunking_strategy=ChunkingStrategy.FIXED_SIZE.value)
    batch: list[str] = []
    idx = 0

    def flush(texts: list[str]) -> None:
        nonlocal idx
        chunks = [
            Chunk(text=t, source_document=source_document,
                  chunking_strategy=ChunkingStrategy.FIXED_SIZE.value, chunk_index=idx + i)
            for i, t in enumerate(texts)
        ]
        idx += len(chunks)
        report.chunks_created += len(chunks)

        embeddings = embedding_client.embed([c.text for c in chunks])
        dedups = check_duplicate_batch(embeddings, vector_store, threshold=dedup_threshold)

        ids, out_texts, metas, embs = [], [], [], []
        for c, emb, dd in zip(chunks, embeddings, dedups):
            if dd.is_duplicate:
                report.duplicates_skipped += 1
                report.duplicate_of.append(dd.duplicate_of)
                continue
            ids.append(c.chunk_id); out_texts.append(c.text); metas.append(c.metadata()); embs.append(emb)

        if ids:
            vector_store.add_many(ids, embs, out_texts, metas)
            report.chunks_inserted += len(ids)
        if progress_cb:
            progress_cb(idx)

    for text in chunk_texts:
        batch.append(text)
        if len(batch) >= batch_size:
            flush(batch)
            batch = []
    if batch:
        flush(batch)
    return report
