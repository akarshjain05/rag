"""LLM-as-judge evaluators for the eval suite.

Judges include:
- AnswerCorrectnessJudge
- FaithfulnessJudge (CoT)
- AnswerRelevanceJudge
- CitationAccuracyJudge
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from rag_api.adapters.llm.llm_client import LLMClient
from rag_api.domain.models import RetrievedChunk
from rag_api.domain.generation.verification import split_into_claims
from eval.golden_dataset import GoldenExample

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_object(raw: str) -> dict | None:
    match = _JSON_OBJECT_RE.search(raw)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def join_chunk_texts(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(f"[{i+1}] ({c.metadata.get('source_document', 'unknown')}) {c.text}" for i, c in enumerate(chunks))


@dataclass
class CorrectnessResult:
    correct: bool | None
    reasoning: str | None = None


class AnswerCorrectnessJudge:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def judge(self, example: GoldenExample, generated_answer: str, mode: str) -> CorrectnessResult:
        if example.is_unanswerable:
            system = (
                "You judge whether an AI system correctly recognized it could not answer a question, because "
                "the question genuinely has no answer in the source documents. Correct behavior is clearly "
                "declining to answer or stating the information isn't available -- NOT fabricating a "
                'plausible-sounding answer. Respond with ONLY a JSON object: {"correct": true, "reasoning": '
                '"..."}. No other text.'
            )
            user = f"Question: {example.question}\n\nSystem's answer: {generated_answer}\n\nSystem's internal mode: {mode}"
        elif example.category == "ambiguous":
            system = (
                "You judge whether an AI system's answer to a genuinely ambiguous or underspecified question is "
                "reasonable. A good answer either surfaces the ambiguity/multiple readings, or picks one "
                "reasonable interpretation and answers it clearly and correctly. A bad answer confidently "
                "asserts one interpretation as the only possible one with no acknowledgment, or is factually "
                'wrong under every reasonable interpretation. Respond with ONLY a JSON object: {"correct": '
                'true, "reasoning": "..."}. No other text.'
            )
            user = (
                f"Question: {example.question}\n\nReference notes on the ambiguity: {example.golden_answer}"
                f"\n\nSystem's answer: {generated_answer}"
            )
        else:
            system = (
                "You judge whether an AI-generated answer conveys the same key factual information as a "
                "reference answer, for a question with a specific correct answer. Minor wording differences are "
                'fine; missing or contradicting a key fact is not. Respond with ONLY a JSON object: {"correct": '
                'true, "reasoning": "..."}. No other text.'
            )
            user = f"Question: {example.question}\n\nReference answer: {example.golden_answer}\n\nSystem's answer: {generated_answer}"

        raw = self.llm_client.generate(system, user)
        parsed = _parse_json_object(raw)
        if parsed is None:
            return CorrectnessResult(correct=None)
        correct = parsed.get("correct")
        return CorrectnessResult(correct=correct if isinstance(correct, bool) else None, reasoning=parsed.get("reasoning"))


@dataclass
class FaithfulnessResult:
    grounded_fraction: float | None
    claim_count: int


class FaithfulnessJudge:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def judge(self, answer: str, retrieved_chunks: list[RetrievedChunk]) -> FaithfulnessResult:
        claims = split_into_claims(answer)
        if not claims:
            return FaithfulnessResult(grounded_fraction=1.0, claim_count=0)

        claims_block = "\n".join(f"Claim {i}: {c.claim_text}" for i, c in enumerate(claims, start=1))
        context = join_chunk_texts(retrieved_chunks)
        system = (
            "You are an expert evaluator. Your task is to evaluate whether each claim in the AI-generated answer is strictly grounded in the provided context.\n"
            "Process each claim step by step (Chain-of-Thought). First, identify which sentences in the context support or contradict the claim. "
            "Then, determine if the claim is fully supported (true) or contains unverified information (false).\n\n"
            'Finally, output a JSON object in this format:\n'
            '{\n'
            '  "reasoning": "1. Claim 1 is supported by... 2. Claim 2 is not supported because...",\n'
            '  "grounded": {"1": true, "2": false}\n'
            '}\n'
            "Ensure the JSON object is the final part of your response."
        )
        user = f"Context:\n\n{context}\n\nClaims:\n\n{claims_block}"

        raw = self.llm_client.generate(system, user)
        parsed = _parse_json_object(raw)
        if parsed is None:
            return FaithfulnessResult(grounded_fraction=None, claim_count=len(claims))

        grounded_field = parsed.get("grounded", {})
        if not isinstance(grounded_field, dict):
            return FaithfulnessResult(grounded_fraction=None, claim_count=len(claims))

        grounded_count = sum(1 for k, v in grounded_field.items() if str(k).isdigit() and 1 <= int(k) <= len(claims) and v is True)
        return FaithfulnessResult(grounded_fraction=grounded_count / len(claims), claim_count=len(claims))


@dataclass
class AnswerRelevanceResult:
    relevance_score: float | None
    reasoning: str | None = None


class AnswerRelevanceJudge:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def judge(self, question: str, answer: str) -> AnswerRelevanceResult:
        system = (
            "Evaluate how relevant the generated answer is to the user's question.\n"
            "An answer is relevant if it directly addresses the question without rambling, adding unnecessary filler, or ignoring the core intent.\n"
            "Use Chain-of-Thought reasoning, then output a JSON object with a score between 0.0 and 1.0 (1.0 = perfectly concise and relevant).\n"
            'Format:\n'
            '{\n'
            '  "reasoning": "...",\n'
            '  "score": 1.0\n'
            '}'
        )
        user = f"Question: {question}\n\nAnswer: {answer}"

        raw = self.llm_client.generate(system, user)
        parsed = _parse_json_object(raw)
        if parsed is None:
            return AnswerRelevanceResult(relevance_score=None)
        score = parsed.get("score")
        return AnswerRelevanceResult(relevance_score=float(score) if score is not None else None, reasoning=parsed.get("reasoning"))


@dataclass
class CitationAccuracyResult:
    accuracy: float | None
    reasoning: str | None = None


class CitationAccuracyJudge:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def judge(self, answer: str, retrieved_chunks: list[RetrievedChunk]) -> CitationAccuracyResult:
        import re
        citation_pattern = re.compile(r'【(\d+)】|\[(\d+)\]')
        citations_found = citation_pattern.findall(answer)
        if not citations_found:
            return CitationAccuracyResult(accuracy=1.0, reasoning="No citations to check.")

        # Extract sentences with citations
        # We'll just pass the answer and the context chunks and ask the LLM to verify every citation marker.
        context = join_chunk_texts(retrieved_chunks)
        system = (
            "You are evaluating the Citation Accuracy of an AI response. The response contains citation markers like [1] or 【1】.\n"
            "Your task is to verify if the text immediately preceding each citation marker is factually supported by the specific source chunk indicated by that number.\n"
            "Use Chain-of-Thought reasoning. Evaluate each cited claim against its referenced chunk. If a claim points to [1], it MUST be supported by chunk 1.\n"
            'Output a JSON object with a boolean for each citation marker instance:\n'
            '{\n'
            '  "reasoning": "...",\n'
            '  "citations_correct": {"1": true, "2": false, "3": true}\n'
            '}'
        )
        user = f"Context:\n\n{context}\n\nAnswer:\n\n{answer}"

        raw = self.llm_client.generate(system, user)
        parsed = _parse_json_object(raw)
        if parsed is None:
            return CitationAccuracyResult(accuracy=None)
        
        citations_correct = parsed.get("citations_correct", {})
        if not isinstance(citations_correct, dict) or not citations_correct:
            return CitationAccuracyResult(accuracy=None, reasoning=parsed.get("reasoning"))

        correct_count = sum(1 for v in citations_correct.values() if v is True)
        return CitationAccuracyResult(
            accuracy=correct_count / len(citations_correct),
            reasoning=parsed.get("reasoning")
        )

@dataclass
class ContextRelevanceResult:
    relevant_chunks: list[bool]
    reasoning: str | None = None

class ContextRelevanceJudge:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def judge(self, question: str, retrieved_chunks: list[RetrievedChunk]) -> ContextRelevanceResult:
        if not retrieved_chunks:
            return ContextRelevanceResult(relevant_chunks=[])

        context = join_chunk_texts(retrieved_chunks)
        system = (
            "You are evaluating the Context Relevance of retrieved search results for a user's question.\n"
            "For each retrieved chunk, determine if it contains sufficient information to directly answer the question (or a substantial part of it).\n"
            "Use Chain-of-Thought reasoning to evaluate each chunk.\n"
            'Output a JSON object with a boolean for each chunk index (1 to N):\n'
            '{\n'
            '  "reasoning": "Chunk 1 contains the exact answer. Chunk 2 is unrelated.",\n'
            '  "chunk_relevance": {"1": true, "2": false}\n'
            '}'
        )
        user = f"Question: {question}\n\nRetrieved Chunks:\n\n{context}"

        raw = self.llm_client.generate(system, user)
        parsed = _parse_json_object(raw)
        
        if parsed is None or not isinstance(parsed.get("chunk_relevance"), dict):
            return ContextRelevanceResult(relevant_chunks=[False] * len(retrieved_chunks))

        chunk_relevance = parsed.get("chunk_relevance", {})
        relevant_chunks = []
        for i in range(1, len(retrieved_chunks) + 1):
            val = chunk_relevance.get(str(i), False)
            relevant_chunks.append(bool(val))

        return ContextRelevanceResult(
            relevant_chunks=relevant_chunks,
            reasoning=parsed.get("reasoning")
        )
