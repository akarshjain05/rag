from __future__ import annotations

from unittest.mock import MagicMock

from rag_api.domain.generation.generation import GenerationResult
from rag_api.domain.models import RetrievedChunk
from eval.eval_runner import format_comparison_report, run_chunking_strategy_comparison, run_eval_suite
from eval.golden_dataset import GoldenExample
from eval.judges import CorrectnessResult, FaithfulnessResult


def chunk(source_document="doc.md"):
    return RetrievedChunk(chunk_id="x", text="t", metadata={"source_document": source_document})


def make_fakes(gen_answer="Answer [1].", gen_mode="llm", coverage=1.0, correct=True, faithfulness=1.0, retrieved=None):
    retriever = MagicMock()
    retriever.retrieve.return_value = retrieved if retrieved is not None else [chunk()]

    generator = MagicMock()
    generator.generate.return_value = GenerationResult(
        answer=gen_answer, mode=gen_mode, citation_coverage=coverage, citation_coverage_basis="verified"
    )

    correctness_judge = MagicMock()
    correctness_judge.judge.return_value = CorrectnessResult(correct=correct, reasoning="because")

    faithfulness_judge = MagicMock()
    faithfulness_judge.judge.return_value = FaithfulnessResult(grounded_fraction=faithfulness, claim_count=1)

    return retriever, generator, correctness_judge, faithfulness_judge


# --------------------------------------------------------------------------
# run_eval_suite
# --------------------------------------------------------------------------
def test_run_eval_suite_produces_one_result_per_example():
    examples = [
        GoldenExample(id="q1", question="Q1?", golden_answer="A1", category="lookup", expected_source_documents=["doc.md"]),
        GoldenExample(id="q2", question="Q2?", golden_answer="A2", category="lookup", expected_source_documents=["doc.md"]),
    ]
    retriever, generator, correctness_judge, faithfulness_judge = make_fakes()

    results = run_eval_suite(examples, retriever, generator, correctness_judge, faithfulness_judge)

    assert len(results) == 2
    assert [r.example_id for r in results] == ["q1", "q2"]


def test_run_eval_suite_populates_all_four_metrics_per_case():
    examples = [GoldenExample(id="q1", question="Q?", golden_answer="A", category="lookup", expected_source_documents=["doc.md"])]
    retriever, generator, correctness_judge, faithfulness_judge = make_fakes(correct=True, faithfulness=0.8, coverage=0.9)

    result = run_eval_suite(examples, retriever, generator, correctness_judge, faithfulness_judge)[0]

    assert result.answer_correct is True
    assert result.faithfulness == 0.8
    assert result.citation_accuracy == 0.9
    assert result.retrieval_relevance == 1.0  # the fake retriever returned doc.md, which matches expected


def test_run_eval_suite_passes_chunking_strategy_through_to_retrieval_and_result():
    examples = [GoldenExample(id="q1", question="Q?", golden_answer="A", category="lookup")]
    retriever, generator, correctness_judge, faithfulness_judge = make_fakes()

    results = run_eval_suite(examples, retriever, generator, correctness_judge, faithfulness_judge, chunking_strategy="semantic")

    retriever.retrieve.assert_called_once_with("Q?", top_k=5, chunking_strategy="semantic")
    assert results[0].chunking_strategy == "semantic"


def test_run_eval_suite_faithfulness_judge_receives_the_retrieved_chunks():
    retrieved = [chunk("a.md"), chunk("b.md")]
    examples = [GoldenExample(id="q1", question="Q?", golden_answer="A", category="lookup")]
    retriever, generator, correctness_judge, faithfulness_judge = make_fakes(retrieved=retrieved)

    run_eval_suite(examples, retriever, generator, correctness_judge, faithfulness_judge)

    faithfulness_judge.judge.assert_called_once_with("Answer [1].", retrieved)


# --------------------------------------------------------------------------
# run_chunking_strategy_comparison / format_comparison_report
# --------------------------------------------------------------------------
def test_comparison_runs_the_suite_once_per_strategy():
    examples = [GoldenExample(id="q1", question="Q?", golden_answer="A", category="lookup", expected_source_documents=["doc.md"])]
    retriever, generator, correctness_judge, faithfulness_judge = make_fakes()

    comparison = run_chunking_strategy_comparison(
        examples, retriever, generator, correctness_judge, faithfulness_judge,
        strategies=["fixed_size", "structure_aware", "semantic"],
    )

    assert set(comparison.keys()) == {"fixed_size", "structure_aware", "semantic"}
    assert retriever.retrieve.call_count == 3
    for strategy_summary in comparison.values():
        assert strategy_summary["overall"]["n"] == 1


def test_format_comparison_report_identifies_the_best_strategy_per_metric():
    comparison = {
        "fixed_size": {"overall": {"answer_correctness": 0.5, "faithfulness": 0.5, "retrieval_relevance": 0.5, "citation_accuracy": 0.5}},
        "structure_aware": {"overall": {"answer_correctness": 0.9, "faithfulness": 0.9, "retrieval_relevance": 0.9, "citation_accuracy": 0.9}},
        "semantic": {"overall": {"answer_correctness": 0.7, "faithfulness": 0.7, "retrieval_relevance": 0.7, "citation_accuracy": 0.7}},
    }

    report = format_comparison_report(comparison)

    assert "structure_aware" in report
    assert report.count("answer_correctness: structure_aware") == 1
    assert "Best strategy per metric" in report


def test_format_comparison_report_handles_missing_metric_values():
    comparison = {
        "fixed_size": {"overall": {"answer_correctness": None, "faithfulness": 0.8, "retrieval_relevance": 0.5, "citation_accuracy": 1.0}},
    }
    report = format_comparison_report(comparison)
    assert "n/a" in report
