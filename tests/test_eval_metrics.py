from __future__ import annotations

from app.models import RetrievedChunk
from eval.metrics import EvalCaseResult, compute_retrieval_relevance, summarize_results


def chunk(source_document):
    return RetrievedChunk(chunk_id="x", text="t", metadata={"source_document": source_document})


# --------------------------------------------------------------------------
# compute_retrieval_relevance
# --------------------------------------------------------------------------
def test_relevance_full_when_all_expected_docs_retrieved():
    retrieved = [chunk("a.md"), chunk("b.md")]
    assert compute_retrieval_relevance(retrieved, ["a.md", "b.md"]) == 1.0


def test_relevance_partial_for_multi_hop_when_only_one_doc_found():
    retrieved = [chunk("a.md"), chunk("c.md")]
    assert compute_retrieval_relevance(retrieved, ["a.md", "b.md"]) == 0.5


def test_relevance_zero_when_none_of_the_expected_docs_found():
    retrieved = [chunk("c.md")]
    assert compute_retrieval_relevance(retrieved, ["a.md"]) == 0.0


def test_relevance_none_for_unanswerable_questions_with_no_expected_docs():
    retrieved = [chunk("a.md")]
    assert compute_retrieval_relevance(retrieved, []) is None


def test_relevance_zero_not_none_when_expected_docs_exist_but_nothing_retrieved():
    assert compute_retrieval_relevance([], ["a.md"]) == 0.0


# --------------------------------------------------------------------------
# summarize_results
# --------------------------------------------------------------------------
def make_result(category, correct=True, faithfulness=1.0, relevance=1.0, citation_accuracy=1.0):
    return EvalCaseResult(
        example_id="x", question="q", category=category, chunking_strategy="structure_aware",
        generated_answer="a", mode="llm", answer_correct=correct, correctness_reasoning=None,
        faithfulness=faithfulness, retrieval_relevance=relevance, citation_accuracy=citation_accuracy,
        citation_coverage_basis="verified",
    )


def test_summarize_overall_averages_across_all_cases():
    results = [make_result("lookup", correct=True, faithfulness=1.0), make_result("lookup", correct=False, faithfulness=0.5)]
    summary = summarize_results(results)
    assert summary["overall"]["n"] == 2
    assert summary["overall"]["answer_correctness"] == 0.5
    assert summary["overall"]["faithfulness"] == 0.75


def test_summarize_breaks_down_by_category():
    results = [make_result("lookup", correct=True), make_result("multi_hop", correct=False)]
    summary = summarize_results(results)
    assert summary["by_category"]["lookup"]["answer_correctness"] == 1.0
    assert summary["by_category"]["multi_hop"]["answer_correctness"] == 0.0
    assert set(summary["by_category"].keys()) == {"lookup", "multi_hop"}


def test_summarize_ignores_none_values_rather_than_treating_as_zero():
    results = [
        make_result("unanswerable", relevance=None),  # relevance not applicable for this category
        make_result("lookup", relevance=1.0),
    ]
    summary = summarize_results(results)
    assert summary["overall"]["retrieval_relevance"] == 1.0  # averaged over the 1 case that had a value, not 0.5


def test_summarize_all_none_metric_returns_none_not_an_error():
    results = [make_result("unanswerable", relevance=None), make_result("unanswerable", relevance=None)]
    summary = summarize_results(results)
    assert summary["overall"]["retrieval_relevance"] is None


def test_summarize_correctness_ignores_unparseable_judge_results():
    results = [make_result("lookup", correct=True), make_result("lookup", correct=None)]
    summary = summarize_results(results)
    assert summary["overall"]["answer_correctness"] == 1.0  # the unparseable case doesn't count as a failure


def test_summarize_empty_results_returns_none_metrics_not_a_crash():
    summary = summarize_results([])
    assert summary["overall"]["n"] == 0
    assert summary["overall"]["answer_correctness"] is None
    assert summary["by_category"] == {}
