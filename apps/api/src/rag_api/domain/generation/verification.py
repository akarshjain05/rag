"""LLM-as-judge citation verification and answer-completeness scoring.

A single batched call does both jobs at once: for every sentence-level claim
in a generated answer, whether its cited excerpt(s) actually support it, and
a 0-1 completeness score for whether the whole answer addresses the whole
question. One call rather than one-per-claim, for the same reason the
reranker's LLM-judge batches -- an N-times-slower verification pass isn't a
defensible trade against the value it adds.

This is the layer described in the project brief as "the quality layer most
RAG systems skip entirely": structural citation-number validation (does [7]
exist at all -- see `generation._extract_and_validate_citations`) catches a
hallucinated reference, but says nothing about whether excerpt [1] actually
supports the specific sentence it's attached to. That's what this checks.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from rag_api.adapters.llm.llm_client import LLMClient
from rag_api.domain.models import ClaimVerification, RetrievedChunk
from rag_api.domain.chunking.text_utils import split_sentences

_CITATION_RE = re.compile(r"\[(\d+)\]")
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def split_into_claims(answer: str) -> list[ClaimVerification]:
    """Split a generated answer into sentence-level claims, each carrying
    the citation marker(s) it referenced (a sentence can carry more than
    one, e.g. "...covered by both policies [1][2]."). Markers are left in
    the claim text on purpose -- the verification prompt benefits from the
    judge seeing exactly what it's being asked to check."""
    claims = []
    for sentence in split_sentences(answer):
        markers = sorted({int(m) for m in _CITATION_RE.findall(sentence)})
        claims.append(ClaimVerification(claim_text=sentence, citation_markers=markers))
    return claims


@dataclass
class VerificationResult:
    claims: list[ClaimVerification]
    completeness: float | None  # None if the judge's response couldn't be parsed


class CitationVerifier:
    def __init__(self, llm_client: LLMClient, strictness: str = "lenient"):
        self.strictness = strictness
        self.llm_client = llm_client

    def verify(self, query: str, answer: str, chunks: list[RetrievedChunk], history: list[dict] | None = None) -> VerificationResult:
        claims = split_into_claims(answer)
        cited_claims = [c for c in claims if c.citation_markers]

        if not cited_claims:
            # nothing citation-backed to check, but still worth a completeness read
            raw = self.llm_client.generate(
                'Rate how completely the answer addresses every part of the question, 0.0-1.0. '
                'Respond with ONLY a JSON object: {"completeness": 0.8}. No other text.',
                f"Question: {query}\n\nAnswer: {answer}",
                history
            )
            _, completeness = self._parse_response(raw, 0)
            return VerificationResult(claims=claims, completeness=completeness)

        # Deduplicate excerpts
        needed_markers = set()
        for c in cited_claims:
            needed_markers.update(c.citation_markers)
        
        excerpts_text = "\n".join(f"Excerpt [{m}]: {self._excerpt_text(chunks, m)}" for m in sorted(needed_markers))
        
        claims_text = "\n".join(f'[claim {i}] "{c.claim_text}" -- cited excerpt(s): {c.citation_markers}' for i, c in enumerate(cited_claims, start=1))
        claims_block = excerpts_text + "\n\n" + claims_text
        system = (
            'Rate each claim: "full" (excerpt fully supports it, including caveats), "partial" (excerpt supports '
            'the core claim but the claim omits a minor caveat/condition present in the excerpt), or "none" '
            '(unsupported or contradicted). Respond with ONLY a JSON object: '
            '{"claims": {"1": "full", "2": "partial"}, "completeness": 0.8} '
            'A claim that states the correct core fact but omits a secondary exception or edge case is still well-supported.'
        )
        user = f"Question: {query}\n\nClaims and excerpts:\n\n{claims_block}"

        raw = self.llm_client.generate(system, user, history)
        supported_map, completeness = self._parse_response(raw, len(cited_claims))

        for i, claim in enumerate(cited_claims, start=1):
            level = supported_map.get(i)
            claim.support_level = level
            if level == "full":
                claim.supported = True
            elif level == "none":
                claim.supported = False
            elif level == "partial":
                claim.supported = True if self.strictness == "lenient" else False
            else:
                claim.supported = None

        return VerificationResult(claims=claims, completeness=completeness)

    @staticmethod
    def _excerpt_text(chunks: list[RetrievedChunk], marker: int) -> str:
        if 1 <= marker <= len(chunks):
            return chunks[marker - 1].text
        return "(citation number out of range -- no such excerpt)"

    @staticmethod
    def _parse_response(raw: str, n_claims: int) -> tuple[dict[int, str], float | None]:
        """Defensive parsing, same shape as the reranker's: a response the
        model didn't format as asked degrades to "couldn't verify" (None
        completeness, no claims marked supported) rather than raising."""
        match = _JSON_OBJECT_RE.search(raw)
        if not match:
            return {}, None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}, None
        if not isinstance(parsed, dict):
            return {}, None

        supported_map: dict[int, str] = {}
        claims_field = parsed.get("claims", {})
        if isinstance(claims_field, dict):
            for key, value in claims_field.items():
                try:
                    idx = int(key)
                except (TypeError, ValueError):
                    continue
                if 1 <= idx <= n_claims and isinstance(value, str):
                    supported_map[idx] = value.lower()

        completeness = None
        try:
            raw_completeness = parsed.get("completeness")
            if raw_completeness is not None:
                completeness = max(0.0, min(1.0, float(raw_completeness)))
        except (TypeError, ValueError):
            completeness = None

        return supported_map, completeness
