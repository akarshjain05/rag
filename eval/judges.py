"""LLM-as-judge evaluators for the eval suite.

Two judges, deliberately checking different things:

- AnswerCorrectnessJudge: does the generated answer convey the same key
  information as the hand-written golden answer? Category-aware -- an
  "unanswerable" question is correct if the system declined rather than
  fabricated; an "ambiguous" question is correct if the answer surfaces the
  ambiguity or clearly answers one reasonable reading, not if it silently
  assumes the only possible reading.

- FaithfulnessJudge: is every claim in the answer grounded in the full
  retrieved context, cited or not? This is broader than the runtime
  citation-accuracy check (`app.verification.CitationVerifier`), which only
  checks claims that already carry a citation marker against their
  specific cited excerpt. An answer can slip in an uncited, hallucinated
  claim while every *cited* claim checks out -- citation accuracy alone
  can't see that; faithfulness is what catches it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.llm_client import LLMClient
from app.models import RetrievedChunk
from app.verification import split_into_claims
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
    return "\n\n".join(f"({c.metadata.get('source_document', 'unknown')}) {c.text}" for c in chunks)


# --------------------------------------------------------------------------
# Answer correctness
# --------------------------------------------------------------------------
@dataclass
class CorrectnessResult:
    correct: bool | None  # None if the judge's response couldn't be parsed
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
        if not isinstance(correct, bool):
            return CorrectnessResult(correct=None, reasoning=parsed.get("reasoning"))
        return CorrectnessResult(correct=correct, reasoning=parsed.get("reasoning"))


# --------------------------------------------------------------------------
# Faithfulness
# --------------------------------------------------------------------------
@dataclass
class FaithfulnessResult:
    grounded_fraction: float | None  # None if nothing could be parsed; 1.0 vacuously if there were no claims
    claim_count: int


class FaithfulnessJudge:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def judge(self, answer: str, retrieved_chunks: list[RetrievedChunk]) -> FaithfulnessResult:
        claims = split_into_claims(answer)
        if not claims:
            return FaithfulnessResult(grounded_fraction=1.0, claim_count=0)

        claims_block = "\n".join(f"[{i}] {c.claim_text}" for i, c in enumerate(claims, start=1))
        context = join_chunk_texts(retrieved_chunks)
        system = (
            "You check whether each numbered claim from an AI-generated answer is grounded in the provided "
            "context -- i.e. a careful reader could verify the claim from the context, regardless of whether "
            'the claim happens to carry a citation marker. Respond with ONLY a JSON object: {"grounded": '
            '{"1": true, "2": false}}. No other text.'
        )
        user = f"Context:\n\n{context}\n\nClaims:\n\n{claims_block}"

        raw = self.llm_client.generate(system, user)
        parsed = _parse_json_object(raw)
        if parsed is None:
            return FaithfulnessResult(grounded_fraction=None, claim_count=len(claims))

        grounded_field = parsed.get("grounded", {})
        if not isinstance(grounded_field, dict):
            return FaithfulnessResult(grounded_fraction=None, claim_count=len(claims))

        grounded_count = 0
        for key, value in grounded_field.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            if 1 <= idx <= len(claims) and value is True:
                grounded_count += 1

        return FaithfulnessResult(grounded_fraction=grounded_count / len(claims), claim_count=len(claims))
