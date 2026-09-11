"""Per-case eval results and aggregation across a run of the golden suite."""
from __future__ import annotations

from dataclasses import dataclass

from rag_api.domain.models import RetrievedChunk


def compute_retrieval_relevance(retrieved_chunks: list[RetrievedChunk], expected_source_documents: list[str]) -> float | None:
    if not expected_source_documents:
        return None
    retrieved_docs = {c.metadata.get("source_document") for c in retrieved_chunks}
    found = sum(1 for doc in expected_source_documents if doc in retrieved_docs)
    return found / len(expected_source_documents)


def compute_recall_at_k(relevant_chunks: list[bool], k: int) -> float | None:
    if not relevant_chunks:
        return None
    return 1.0 if any(relevant_chunks[:k]) else 0.0


def compute_ndcg_at_k(relevant_chunks: list[bool], k: int) -> float | None:
    import math
    if not relevant_chunks:
        return None
    
    dcg = 0.0
    for i, is_relevant in enumerate(relevant_chunks[:k]):
        if is_relevant:
            dcg += 1.0 / math.log2(i + 2)
            
    # Ideal DCG: best case is all 1s at the top, up to the number of actual relevant chunks in the whole list
    num_relevant = sum(relevant_chunks)
    idcg = 0.0
    for i in range(min(k, num_relevant)):
        idcg += 1.0 / math.log2(i + 2)
        
    return dcg / idcg if idcg > 0.0 else 0.0


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
    recall_at_5: float | None
    ndcg_at_10: float | None
    answer_relevance: float | None
    citation_accuracy: float | None
    citation_coverage: float | None
    citation_coverage_basis: str | None
    retrieval_confidence: float | None
    used_citation_markers_count: int
    retrieved_chunks_count: int
    ttft: float | None
    total_latency: float | None
    cost: float | None


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
        "recall_at_5": _mean([r.recall_at_5 for r in results]),
        "ndcg_at_10": _mean([r.ndcg_at_10 for r in results]),
        "answer_relevance": _mean([r.answer_relevance for r in results]),
        "citation_accuracy": _mean([r.citation_accuracy for r in results]),
        "citation_coverage": _mean([r.citation_coverage for r in results]),
        "source_panel_precision": _mean(source_panel_precisions),
        "ttft_avg": _mean([r.ttft for r in results]),
        "total_latency_avg": _mean([r.total_latency for r in results]),
        "total_cost": sum(r.cost for r in results if r.cost is not None),
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
