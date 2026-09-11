"""Runs the golden Q&A dataset through the real retrieval + generation
pipeline and scores every case on all four metrics, plus a chunking
strategy comparison built on top of the same run.
"""
from __future__ import annotations

from rag_api.domain.generation.generation import AnswerGenerator
from rag_api.domain.retrieval.retrieval import HybridRetriever
from eval.golden_dataset import GoldenExample
from eval.judges import AnswerCorrectnessJudge, FaithfulnessJudge, AnswerRelevanceJudge, CitationAccuracyJudge
from eval.metrics import EvalCaseResult, compute_retrieval_relevance, summarize_results


def run_eval_suite(
    examples: list[GoldenExample],
    retriever: HybridRetriever,
    generator: AnswerGenerator,
    correctness_judge: AnswerCorrectnessJudge,
    faithfulness_judge: FaithfulnessJudge,
    answer_relevance_judge: AnswerRelevanceJudge,
    citation_accuracy_judge: CitationAccuracyJudge,
    *,
    chunking_strategy: str | None = None,
    top_k: int = 5,
) -> list[EvalCaseResult]:
    results = []
    for example in examples:
        chunks = retriever.retrieve(example.question, top_k=top_k, chunking_strategy=chunking_strategy)
        import time
        import openai
        
        while True:
            try:
                gen_result = generator.generate(example.question, chunks)
                break
            except openai.RateLimitError:
                print("Rate limit reached. Sleeping 5 seconds...")
                time.sleep(5)

        while True:
            try:
                correctness = correctness_judge.judge(example, gen_result.answer, gen_result.mode)
                break
            except openai.RateLimitError:
                time.sleep(5)
        while True:
            try:
                faithfulness = faithfulness_judge.judge(gen_result.answer, chunks)
                break
            except openai.RateLimitError:
                time.sleep(5)
        while True:
            try:
                ans_relevance = answer_relevance_judge.judge(example.question, gen_result.answer)
                break
            except openai.RateLimitError:
                time.sleep(5)
        while True:
            try:
                cit_accuracy = citation_accuracy_judge.judge(gen_result.answer, chunks)
                break
            except openai.RateLimitError:
                time.sleep(5)

        relevance = compute_retrieval_relevance(chunks, example.expected_source_documents)

        results.append(
            EvalCaseResult(
                example_id=example.id,
                question=example.question,
                category=example.category,
                chunking_strategy=chunking_strategy or "default",
                generated_answer=gen_result.answer,
                mode=gen_result.mode,
                answer_correct=correctness.correct,
                correctness_reasoning=correctness.reasoning,
                faithfulness=faithfulness.grounded_fraction,
                retrieval_relevance=relevance,
                answer_relevance=ans_relevance.relevance_score,
                citation_accuracy=cit_accuracy.accuracy,
                citation_coverage=gen_result.citation_coverage,
                citation_coverage_basis=gen_result.citation_coverage_basis,
                retrieval_confidence=gen_result.retrieval_confidence,
                used_citation_markers_count=len(gen_result.used_citation_markers),
                retrieved_chunks_count=len(chunks),
            )
        )
    return results


def run_chunking_strategy_comparison(
    examples: list[GoldenExample],
    retriever: HybridRetriever,
    generator: AnswerGenerator,
    correctness_judge: AnswerCorrectnessJudge,
    faithfulness_judge: FaithfulnessJudge,
    answer_relevance_judge: AnswerRelevanceJudge,
    citation_accuracy_judge: CitationAccuracyJudge,
    *,
    strategies: list[str],
    top_k: int = 5,
) -> dict[str, dict]:
    return {
        strategy: summarize_results(
            run_eval_suite(examples, retriever, generator, correctness_judge, faithfulness_judge, answer_relevance_judge, citation_accuracy_judge, chunking_strategy=strategy, top_k=top_k)
        )
        for strategy in strategies
    }


_METRICS = ["answer_correctness", "faithfulness", "retrieval_relevance", "answer_relevance", "citation_accuracy", "citation_coverage"]


def format_comparison_report(comparison: dict[str, dict]) -> str:
    header = f"{'Strategy':<18}" + "".join(f"{m:<20}" for m in _METRICS)
    lines = [header, "-" * len(header)]

    for strategy, summary in comparison.items():
        row = f"{strategy:<18}"
        for metric in _METRICS:
            value = summary["overall"][metric]
            row += f"{value:<20.1%}" if value is not None else f"{'n/a':<20}"
        lines.append(row)

    lines.append("\nBest strategy per metric:")
    for metric in _METRICS:
        scored = {s: summary["overall"][metric] for s, summary in comparison.items() if summary["overall"][metric] is not None}
        best = max(scored, key=scored.get) if scored else "n/a (no data)"
        lines.append(f"  {metric}: {best}")

    return "\n".join(lines)
