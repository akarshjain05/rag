"""Per-case eval results and aggregation across a run of the golden suite."""
from __future__ import annotations

from dataclasses import dataclass

from app.models import RetrievedChunk


def compute_retrieval_relevance(retrieved_chunks: list[RetrievedChunk], expected_source_documents: list[str]) -> float | None:
    """Fraction of `expected_source_documents` that appear among the
    retrieved chunks' source documents -- recall of the documents that
    should have been found. Returns None (not just 0.0) when
    `expected_source_documents` is empty: that's the "unanswerable"
    category, where there's nothing correct to retrieve, so "were the
    right chunks retrieved" isn't a meaningful question to score -- forcing
    a number there would silently corrupt the average for every other
    question that does have a real answer to be found."""
    if not expected_source_documents:
        return None
    retrieved_docs = {c.metadata.get("source_document") for c in retrieved_chunks}
    found = sum(1 for doc in expected_source_documents if doc in retrieved_docs)
    return found / len(expected_source_documents)


@dataclass
class EvalCaseResult:
    example_id: str
    question: str
    category: str
    chunking_strategy: str
    generated_answer: str
    mode: str
    answer_correct: bool | None
    correctness_reasoning: str | None
    faithfulness: float | None
    retrieval_relevance: float | None
    citation_accuracy: float | None
    citation_coverage_basis: str | None


def _mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def _correctness_mean(results: list[EvalCaseResult]) -> float | None:
    return _mean([1.0 if r.answer_correct else 0.0 for r in results if r.answer_correct is not None])


def _summarize_group(results: list[EvalCaseResult]) -> dict:
    return {
        "n": len(results),
        "answer_correctness": _correctness_mean(results),
        "faithfulness": _mean([r.faithfulness for r in results]),
        "retrieval_relevance": _mean([r.retrieval_relevance for r in results]),
        "citation_accuracy": _mean([r.citation_accuracy for r in results]),
    }


def summarize_results(results: list[EvalCaseResult]) -> dict:
    """{"overall": {...}, "by_category": {"lookup": {...}, "multi_hop": {...}, ...}}
    Every metric is a mean over whichever cases actually produced a value
    for it (see `_mean`) -- a case where a metric is structurally not
    applicable (e.g. retrieval_relevance on an unanswerable question)
    doesn't get counted as a failure, and doesn't get silently zeroed
    into the average either."""
    by_category = {
        category: _summarize_group([r for r in results if r.category == category])
        for category in sorted({r.category for r in results})
    }
    return {"overall": _summarize_group(results), "by_category": by_category}
