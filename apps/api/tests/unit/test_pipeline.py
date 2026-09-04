from __future__ import annotations

from pathlib import Path

from rag_api.domain.models import ChunkingStrategy
from rag_api.services.ingest_service import IngestionPipeline


def make_pipeline(fake_embedder, vector_store, sparse_index, **overrides):
    kwargs = dict(
        default_strategy=ChunkingStrategy.STRUCTURE_AWARE,
        fixed_chunk_size=500,
        fixed_chunk_overlap=50,
        structure_max_section_size=500,
        dedup_similarity_threshold=0.95,
    )
    kwargs.update(overrides)
    return IngestionPipeline(fake_embedder, vector_store, sparse_index, **kwargs)


def test_ingest_single_file_populates_both_indexes(fake_embedder, vector_store, sparse_index, md_path):
    pipeline = make_pipeline(fake_embedder, vector_store, sparse_index)

    report = pipeline.ingest_file(md_path)

    assert report.error is None
    assert report.chunks_created > 0
    assert report.chunks_inserted == report.chunks_created
    assert report.duplicates_skipped == 0

    assert vector_store.count() == report.chunks_inserted
    assert sparse_index.count() == vector_store.count()
    # both indexes hold exactly the same chunk ids -- proof they're in sync
    assert set(sparse_index.chunk_ids()) == {r["chunk_id"] for r in vector_store.get_all()}


def test_reingesting_identical_file_is_fully_deduplicated(fake_embedder, vector_store, sparse_index, md_path):
    pipeline = make_pipeline(fake_embedder, vector_store, sparse_index)

    first = pipeline.ingest_file(md_path)
    second = pipeline.ingest_file(md_path)

    assert first.chunks_inserted == first.chunks_created
    assert second.chunks_inserted == 0
    assert second.duplicates_skipped == second.chunks_created
    assert vector_store.count() == first.chunks_inserted  # nothing new got added


def test_ingest_tracks_chunking_strategy_in_metadata(fake_embedder, vector_store, sparse_index, md_path):
    pipeline = make_pipeline(fake_embedder, vector_store, sparse_index)
    pipeline.ingest_file(md_path, strategy=ChunkingStrategy.FIXED_SIZE)

    rows = vector_store.get_all()
    assert all(r["metadata"]["chunking_strategy"] == "fixed_size" for r in rows)


def test_ingest_semantic_strategy_end_to_end(fake_embedder, vector_store, sparse_index, md_path):
    pipeline = make_pipeline(fake_embedder, vector_store, sparse_index, semantic_similarity_threshold=0.5,
                              semantic_max_chunk_chars=800, semantic_min_chunk_chars=50)
    report = pipeline.ingest_file(md_path, strategy=ChunkingStrategy.SEMANTIC)

    assert report.error is None
    assert report.chunks_inserted > 0
    assert all(r["metadata"]["chunking_strategy"] == "semantic" for r in vector_store.get_all())


def test_ingest_files_batch_syncs_sparse_index_once(fake_embedder, vector_store, sparse_index, md_path, txt_path, html_path):
    pipeline = make_pipeline(fake_embedder, vector_store, sparse_index)

    reports = pipeline.ingest_files([md_path, txt_path, html_path])

    assert len(reports) == 3
    assert all(r.error is None for r in reports)
    assert sparse_index.count() == vector_store.count()
    assert vector_store.count() == sum(r.chunks_inserted for r in reports)


def test_ingest_files_batch_survives_one_bad_file(fake_embedder, vector_store, sparse_index, md_path, tmp_path):
    bad_file = tmp_path / "bad.docx"
    bad_file.write_text("unsupported type")

    pipeline = make_pipeline(fake_embedder, vector_store, sparse_index)
    reports = pipeline.ingest_files([md_path, bad_file])

    by_name = {r.source_file: r for r in reports}
    assert by_name["sample.md"].error is None
    assert by_name["sample.md"].chunks_inserted > 0
    assert by_name["bad.docx"].error is not None
    assert by_name["bad.docx"].chunks_inserted == 0
    # the good file's chunks still made it into the index
    assert vector_store.count() == by_name["sample.md"].chunks_inserted


def test_ingest_pdf_preserves_page_numbers_through_pipeline(fake_embedder, vector_store, sparse_index, pdf_path):
    pipeline = make_pipeline(fake_embedder, vector_store, sparse_index, fixed_chunk_size=1000, fixed_chunk_overlap=0)
    report = pipeline.ingest_file(pdf_path, strategy=ChunkingStrategy.FIXED_SIZE)

    assert report.error is None
    pages = {r["metadata"]["page_number"] for r in vector_store.get_all()}
    assert pages == {1, 2}
