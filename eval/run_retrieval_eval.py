"""Retrieval quality evaluation: dense-only vs sparse-only (BM25) vs hybrid
(RRF), scored with Recall@k and MRR on a labeled query set.

This is the quantitative case for hybrid search, not just an assertion of
it: run it against your own corpus and you get real numbers showing
whether hybrid actually beats either retriever alone on *your* documents,
and by how much.

Usage:
    python eval/run_retrieval_eval.py --sample
        Self-contained demo: ingests a tiny bundled policy-doc corpus and
        evaluates 5 labeled queries against it. No setup beyond the
        embedding provider being configured (works with
        EMBEDDING_PROVIDER=local for zero API keys).

    python eval/run_retrieval_eval.py --dataset queries.json --docs-dir ./my_docs
        Evaluate your own corpus. queries.json is a JSON list of
        {"query": "...", "expected_source": "filename.md"} objects —
        expected_source must exactly match a filename under --docs-dir.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # allow `python eval/run_retrieval_eval.py`

from rag_api.core.settings import get_settings  # noqa: E402
from rag_api.adapters.vectorstore.embeddings import build_embedding_client  # noqa: E402
from rag_api.adapters.storage.loaders import SUPPORTED_EXTENSIONS  # noqa: E402
from rag_api.domain.models import ChunkingStrategy  # noqa: E402
from rag_api.services.ingest_service import IngestionPipeline  # noqa: E402
from rag_api.domain.retrieval.retrieval import reciprocal_rank_fusion  # noqa: E402
from rag_api.adapters.vectorstore.sparse_index import SparseIndex  # noqa: E402
from rag_api.adapters.vectorstore.vector_store import VectorStore  # noqa: E402

SAMPLE_DOCS = {
    "vacation_policy.md": (
        "# Vacation Policy\n\nEmployees accrue vacation days at a rate of 1.5 days per month. "
        "Unused vacation carries over up to a maximum of 10 days into the next calendar year."
    ),
    "remote_work.md": (
        "# Remote Work Policy\n\nEmployees may work remotely up to three days per week with "
        "manager approval. Core hours are 10am-4pm local time."
    ),
    "expense_policy.md": (
        "# Expense Policy\n\nAll expenses over $50 require a submitted receipt. Reimbursement "
        "requests are processed within two weeks through the finance portal."
    ),
    "security_policy.md": (
        "# Security Policy\n\nAll employee laptops must have full-disk encryption enabled. "
        "Passwords must be rotated every 90 days and multi-factor authentication is mandatory."
    ),
}

SAMPLE_QUERIES = [
    {"query": "how many vacation days do employees accrue per month", "expected_source": "vacation_policy.md"},
    {"query": "how many days per week can I work from home", "expected_source": "remote_work.md"},
    {"query": "what is the receipt requirement for expenses", "expected_source": "expense_policy.md"},
    {"query": "how often must passwords be changed", "expected_source": "security_policy.md"},
    {"query": "is multi-factor authentication required", "expected_source": "security_policy.md"},
]


def _build_sample_corpus(tmp_dir: Path) -> list[Path]:
    paths = []
    for name, content in SAMPLE_DOCS.items():
        p = tmp_dir / name
        p.write_text(content)
        paths.append(p)
    return paths


def _extract_sources(ranked: list) -> list[str | None]:
    sources = []
    for r in ranked:
        meta = r["metadata"] if isinstance(r, dict) else r.metadata
        sources.append(meta.get("source_document"))
    return sources


def evaluate(
    dataset: list[dict],
    embedding_client,
    vector_store: VectorStore,
    sparse_index: SparseIndex,
    *,
    top_k: int = 5,
    dense_fetch_k: int = 10,
    sparse_fetch_k: int = 10,
    rrf_k: int = 60,
) -> dict:
    """For each {query, expected_source} pair, check whether expected_source
    appears in the top_k results of dense-only, sparse-only, and hybrid
    (RRF) retrieval. dense/sparse baselines take the top_k of their own
    ranked list; hybrid fuses the full dense_fetch_k/sparse_fetch_k pools
    down to top_k -- exactly how each is actually used in `HybridRetriever`,
    so the comparison reflects real usage rather than an inflated pool for
    hybrid alone. Returns {"dense": {"recall_at_k", "mrr"}, "sparse": ..., "hybrid": ...}."""
    hits = {"dense": 0, "sparse": 0, "hybrid": 0}
    reciprocal_ranks: dict[str, list[float]] = {"dense": [], "sparse": [], "hybrid": []}

    for item in dataset:
        query_embedding = embedding_client.embed([item["query"]])[0]
        dense_pool = vector_store.query(query_embedding, top_k=dense_fetch_k)
        sparse_pool = sparse_index.query(item["query"], top_k=sparse_fetch_k)
        hybrid = reciprocal_rank_fusion(dense_pool, sparse_pool, k=rrf_k, top_k=top_k)

        for mode, ranked in (("dense", dense_pool[:top_k]), ("sparse", sparse_pool[:top_k]), ("hybrid", hybrid)):
            sources = _extract_sources(ranked)
            if item["expected_source"] in sources:
                hits[mode] += 1
                reciprocal_ranks[mode].append(1.0 / (sources.index(item["expected_source"]) + 1))
            else:
                reciprocal_ranks[mode].append(0.0)

    n = len(dataset) or 1
    return {
        mode: {"recall_at_k": hits[mode] / n, "mrr": sum(reciprocal_ranks[mode]) / n}
        for mode in ("dense", "sparse", "hybrid")
    }


def _print_report(summary: dict, top_k: int) -> None:
    col = f"Recall@{top_k}"
    print(f"\n{'Mode':<10}{col:<14}{'MRR':<10}")
    print("-" * 34)
    for mode in ("dense", "sparse", "hybrid"):
        r = summary[mode]
        print(f"{mode:<10}{r['recall_at_k']:<14.1%}{r['mrr']:<10.3f}")
    best = max(summary, key=lambda m: (summary[m]["recall_at_k"], summary[m]["mrr"]))
    print(f"\nBest on this query set: {best}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", action="store_true", help="Run against the bundled sample corpus")
    parser.add_argument("--dataset", type=Path, help="JSON file of {query, expected_source} objects")
    parser.add_argument("--docs-dir", type=Path, help="Directory of documents to ingest (used with --dataset)")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--chunking-strategy", default="structure_aware", choices=[s.value for s in ChunkingStrategy]
    )
    args = parser.parse_args()

    if not args.sample and not (args.dataset and args.docs_dir):
        parser.error("provide --sample, or both --dataset and --docs-dir")

    settings = get_settings()
    embedding_client = build_embedding_client(
        settings.embedding_provider,
        openai_model=settings.openai_embedding_model,
        openai_api_key=settings.openai_api_key,
        local_model=settings.local_embedding_model,
    )
    print(f"Embedding provider: {settings.embedding_provider}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        vector_store = VectorStore(tmp_path / "chroma", "eval_collection")
        sparse_index = SparseIndex()
        pipeline = IngestionPipeline(
            embedding_client, vector_store, sparse_index, default_strategy=ChunkingStrategy(args.chunking_strategy)
        )

        if args.sample:
            doc_paths = _build_sample_corpus(tmp_path)
            dataset = SAMPLE_QUERIES
        else:
            dataset = json.loads(args.dataset.read_text())
            doc_paths = [p for p in sorted(args.docs_dir.iterdir()) if p.suffix.lower() in SUPPORTED_EXTENSIONS]
            if not doc_paths:
                parser.error(f"no supported documents found in {args.docs_dir}")

        print(f"Ingesting {len(doc_paths)} document(s), strategy={args.chunking_strategy}...")
        for report in pipeline.ingest_files(doc_paths):
            status = f"ERROR: {report.error}" if report.error else f"{report.chunks_inserted} chunks inserted"
            print(f"  {report.source_file}: {status}")

        print(f"\nEvaluating {len(dataset)} queries at top_k={args.top_k}...")
        summary = evaluate(dataset, embedding_client, vector_store, sparse_index, top_k=args.top_k, rrf_k=settings.rrf_k)
        _print_report(summary, args.top_k)


if __name__ == "__main__":
    main()
