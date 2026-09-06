"""Run the golden Q&A eval suite against the real pipeline.

Usage:
    python eval/run_eval_suite.py
        Runs the bundled 57-example golden dataset against the bundled
        golden_corpus/, under the configured default chunking strategy.

    python eval/run_eval_suite.py --compare-chunking-strategies
        Ingests golden_corpus/ under all three chunking strategies (safe --
        chunk IDs are namespaced by strategy) and runs the full suite
        against each, printing a side-by-side comparison report.

    python eval/run_eval_suite.py --dataset my_qa.json --docs-dir my_docs/
        Evaluate your own golden dataset and corpus. my_qa.json is a JSON
        list of {"id", "question", "golden_answer", "category",
        "expected_source_documents", "notes"} objects -- see
        eval/golden_dataset.py and eval/golden_qa.json for the format.

Needs a real LLM (LLM_PROVIDER=anthropic or openai): answer correctness and
faithfulness are both LLM-judge metrics. There's no zero-API-key mode for
this one -- judging quality requires a judge.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # allow `python eval/run_eval_suite.py`

from rag_api.core.settings import get_settings  # noqa: E402
from rag_api.adapters.vectorstore.embeddings import build_embedding_client  # noqa: E402
from rag_api.domain.generation.generation import AnswerGenerator  # noqa: E402
from rag_api.adapters.llm.llm_client import build_llm_client  # noqa: E402
from rag_api.adapters.storage.loaders import SUPPORTED_EXTENSIONS  # noqa: E402
from rag_api.domain.models import ChunkingStrategy  # noqa: E402
from rag_api.services.ingest_service import IngestionPipeline  # noqa: E402
from rag_api.domain.retrieval.retrieval import HybridRetriever  # noqa: E402
from rag_api.adapters.vectorstore.sparse_index import SparseIndex  # noqa: E402
from rag_api.adapters.vectorstore.vector_store import VectorStore  # noqa: E402
from rag_api.domain.generation.verification import CitationVerifier  # noqa: E402
from eval.eval_runner import format_comparison_report, run_chunking_strategy_comparison, run_eval_suite  # noqa: E402
from eval.golden_dataset import load_golden_dataset  # noqa: E402
from eval.judges import AnswerCorrectnessJudge, FaithfulnessJudge  # noqa: E402
from eval.metrics import summarize_results  # noqa: E402

DEFAULT_DATASET = Path(__file__).parent / "golden_qa.json"
DEFAULT_CORPUS = Path(__file__).parent / "golden_corpus"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--compare-chunking-strategies", action="store_true")
    parser.add_argument(
        "--chunking-strategy", default="structure_aware", choices=[s.value for s in ChunkingStrategy]
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    settings = get_settings()
    embedding_client = build_embedding_client(
        settings.embedding_provider,
        openai_model=settings.openai_embedding_model,
        openai_api_key=settings.openai_api_key,
        local_model=settings.local_embedding_model,
    )
    llm_client = build_llm_client(
        settings.llm_provider,
        model=settings.anthropic_model if settings.llm_provider == "anthropic" else settings.openai_llm_model,
        api_key=settings.anthropic_api_key if settings.llm_provider == "anthropic" else settings.openai_api_key,
    )
    if llm_client is None:
        raise SystemExit(
            "The eval suite needs a real LLM -- answer correctness and faithfulness are both LLM-judge "
            "metrics. Set LLM_PROVIDER to 'anthropic' or 'openai' (not 'none')."
        )

    examples = load_golden_dataset(args.dataset)
    doc_paths = [p for p in sorted(args.docs_dir.iterdir()) if p.suffix.lower() in SUPPORTED_EXTENSIONS]
    if not doc_paths:
        parser.error(f"no supported documents found in {args.docs_dir}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        vector_store = VectorStore(tmp_path / "chroma", "eval_collection")
        sparse_index = SparseIndex()
        pipeline = IngestionPipeline(embedding_client, vector_store, sparse_index)
        retriever = HybridRetriever(
            embedding_client, vector_store, dense_top_k=args.top_k * 2, sparse_top_k=args.top_k * 2
        )
        generator = AnswerGenerator(
            llm_client,
            mode="llm",
            citation_verifier=CitationVerifier(llm_client),
            low_confidence_threshold=settings.low_confidence_threshold,
        )
        correctness_judge = AnswerCorrectnessJudge(llm_client)
        faithfulness_judge = FaithfulnessJudge(llm_client)

        print(f"Loaded {len(examples)} golden examples from {args.dataset}")

        if args.compare_chunking_strategies:
            strategies = [s.value for s in ChunkingStrategy]
            print(f"Ingesting {len(doc_paths)} document(s) under all {len(strategies)} chunking strategies...")
            for strategy in strategies:
                reports = pipeline.ingest_files(doc_paths, strategy=ChunkingStrategy(strategy))
                print(f"  {strategy}: {sum(r.chunks_inserted for r in reports)} chunks")

            print(f"\nRunning {len(examples)} examples x {len(strategies)} strategies (this makes real LLM calls)...")
            comparison = run_chunking_strategy_comparison(
                examples, retriever, generator, correctness_judge, faithfulness_judge, strategies=strategies, top_k=args.top_k
            )
            print()
            print(format_comparison_report(comparison))
        else:
            print(f"Ingesting {len(doc_paths)} document(s), strategy={args.chunking_strategy}...")
            reports = pipeline.ingest_files(doc_paths, strategy=ChunkingStrategy(args.chunking_strategy))
            print(f"  {sum(r.chunks_inserted for r in reports)} chunks inserted")

            print(f"\nRunning {len(examples)} examples (this makes real LLM calls)...")
            results = run_eval_suite(
                examples, retriever, generator, correctness_judge, faithfulness_judge,
                chunking_strategy=args.chunking_strategy, top_k=args.top_k,
            )
            print()
            print(json.dumps(summarize_results(results), indent=2))


if __name__ == "__main__":
    main()
