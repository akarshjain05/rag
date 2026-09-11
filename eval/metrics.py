"""Per-case eval results and aggregation across a run of the golden suite."""
from __future__ import annotations

from dataclasses import dataclass

from rag_api.domain.models import RetrievedChunk


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
    retrieval_confidence: float | None
    used_citation_markers_count: int
    retrieved_chunks_count: int


def _mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def _correctness_mean(results: list[EvalCaseResult]) -> float | None:
    return _mean([1.0 if r.answer_correct else 0.0 for r in results if r.answer_correct is not None])


def _summarize_group(results: list[EvalCaseResult]) -> dict:
    source_panel_precisions = [
        (r.used_citation_markers_count / r.retrieved_chunks_count)
        for r in results if r.retrieved_chunks_count > 0
    ]
    
    return {
        "n": len(results),
        "answer_correctness": _correctness_mean(results),
        "faithfulness": _mean([r.faithfulness for r in results]),
        "retrieval_relevance": _mean([r.retrieval_relevance for r in results]),
        "citation_accuracy": _mean([r.citation_accuracy for r in results]),
        "source_panel_precision": _mean(source_panel_precisions),
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
    
    # Confidence Calibration Buckets
    buckets = {"0.0-0.3": [], "0.3-0.6": [], "0.6-0.8": [], "0.8-1.0": []}
    for r in results:
        conf = r.retrieval_confidence
        if conf is not None:
            if conf <= 0.3: buckets["0.0-0.3"].append(r)
            elif conf <= 0.6: buckets["0.3-0.6"].append(r)
            elif conf <= 0.8: buckets["0.6-0.8"].append(r)
            else: buckets["0.8-1.0"].append(r)
            
    calibration = {
        label: {
            "n": len(b),
            "answer_correctness": _correctness_mean(b) if b else None
        }
        for label, b in buckets.items()
    }
    
    return {
        "overall": _summarize_group(results),
        "by_category": by_category,
        "confidence_calibration": calibration
    }
