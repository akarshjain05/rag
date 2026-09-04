from __future__ import annotations

from rag_api.domain.models import ChunkingStrategy
from rag_api.services.ingest_service import IngestionPipeline
from eval.run_retrieval_eval import SAMPLE_DOCS, SAMPLE_QUERIES, _build_sample_corpus, evaluate


def test_sample_queries_reference_real_sample_docs():
    doc_names = set(SAMPLE_DOCS.keys())
    for q in SAMPLE_QUERIES:
        assert q["expected_source"] in doc_names


def test_build_sample_corpus_writes_all_docs(tmp_path):
    paths = _build_sample_corpus(tmp_path)
    assert len(paths) == len(SAMPLE_DOCS)
    for p in paths:
        assert p.exists()
        assert p.read_text() == SAMPLE_DOCS[p.name]


def test_evaluate_shape_and_bounds(fake_embedder, vector_store, sparse_index, tmp_path):
    doc_paths = _build_sample_corpus(tmp_path)
    pipeline = IngestionPipeline(fake_embedder, vector_store, sparse_index, default_strategy=ChunkingStrategy.STRUCTURE_AWARE)
    pipeline.ingest_files(doc_paths)

    summary = evaluate(SAMPLE_QUERIES, fake_embedder, vector_store, sparse_index, top_k=3)

    assert set(summary.keys()) == {"dense", "sparse", "hybrid"}
    for mode in summary:
        assert set(summary[mode].keys()) == {"recall_at_k", "mrr"}
        assert 0.0 <= summary[mode]["recall_at_k"] <= 1.0
        assert 0.0 <= summary[mode]["mrr"] <= 1.0


def test_evaluate_achieves_perfect_recall_on_the_small_well_separated_sample_corpus(fake_embedder, vector_store, sparse_index, tmp_path):
    """The bundled sample corpus is deliberately easy (4 short, topically
    distinct docs, 5 unambiguous queries) so --sample is a fast smoke test.
    Every mode should find the right doc every time here; the harness earns
    its keep on harder, larger, real corpora where the three modes diverge."""
    doc_paths = _build_sample_corpus(tmp_path)
    pipeline = IngestionPipeline(fake_embedder, vector_store, sparse_index, default_strategy=ChunkingStrategy.STRUCTURE_AWARE)
    pipeline.ingest_files(doc_paths)

    summary = evaluate(SAMPLE_QUERIES, fake_embedder, vector_store, sparse_index, top_k=3)

    for mode in ("dense", "sparse", "hybrid"):
        assert summary[mode]["recall_at_k"] == 1.0
        assert summary[mode]["mrr"] >= 0.9


def test_evaluate_empty_dataset_returns_zeroed_summary(fake_embedder, vector_store, sparse_index):
    summary = evaluate([], fake_embedder, vector_store, sparse_index)
    for mode in ("dense", "sparse", "hybrid"):
        assert summary[mode]["recall_at_k"] == 0.0
        assert summary[mode]["mrr"] == 0.0


def test_evaluate_empty_index_scores_all_misses(fake_embedder, vector_store, sparse_index):
    summary = evaluate(SAMPLE_QUERIES, fake_embedder, vector_store, sparse_index)
    for mode in ("dense", "sparse", "hybrid"):
        assert summary[mode]["recall_at_k"] == 0.0
