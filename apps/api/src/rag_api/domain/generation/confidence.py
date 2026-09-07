"""Composite answer-confidence scoring.

Three sub-scores, each already on a comparable [0,1] scale, combined by a
plain unweighted mean -- documented as exactly that rather than dressed up
as a calibrated probability. All three are still returned individually
(see `generation.GenerationResult`) so a caller wanting a different
weighting can recompute one without needing this module's opinion baked in.
"""
from __future__ import annotations

from rag_api.domain.models import ClaimVerification, RetrievedChunk


def compute_retrieval_confidence(chunks: list[RetrievedChunk]) -> float:
    """Calculates calibrated retrieval confidence using exponential decay.
    Prevents low-scoring tail chunks from dragging down a strong top hit.

    When a reranker is active, its score is blended with (not replacing)
    dense similarity -- 70% rerank / 30% dense -- rather than letting the
    reranker have sole veto power. `normalize_query` fixing the query
    upstream (services/query_condensation.py) is the primary defense
    against a garbled cross-encoder comparison; this is a secondary
    safeguard for any other case where one signal disagrees sharply with
    another."""
    import numpy as np

    if not chunks:
        return 0.0

    def _decayed(values: list[float]) -> float:
        scores = sorted(values, reverse=True)
        if not scores:
            return 0.0
        weights = [0.5 ** i for i in range(len(scores))]
        return float(np.average(scores, weights=weights))

    dense_score = _decayed([c.dense_similarity if c.dense_similarity is not None else 0.0 for c in chunks])

    if any(c.rerank_score is not None for c in chunks):
        rerank_score = _decayed([c.rerank_score if c.rerank_score is not None else 0.0 for c in chunks])
        calibrated_score = 0.7 * rerank_score + 0.3 * dense_score
    else:
        calibrated_score = dense_score

    return float(max(0.0, min(1.0, round(calibrated_score, 4))))


def compute_citation_coverage(claims: list[ClaimVerification]) -> tuple[float, str]:
    """Fraction of claims judged well-cited, and which basis was used:
    - "verified":   claim has >=1 citation AND an LLM judge confirmed it's
                     supported (used whenever verification actually ran)
    - "structural": claim has >=1 citation at all -- the only thing
                     checkable when no judge ran, so don't claim otherwise

    No claims at all -> (1.0, "structural"): vacuously fully covered, since
    there's nothing left uncited or unsupported.
    """
    if not claims:
        return 1.0, "structural"

    verification_ran = any(c.supported is not None for c in claims)
    if verification_ran:
        good = sum(1 for c in claims if c.citation_markers and c.supported)
        return good / len(claims), "verified"

    good = sum(1 for c in claims if c.citation_markers)
    return good / len(claims), "structural"


def compute_composite_confidence(
    retrieval_confidence: float | None,
    citation_coverage: float | None,
    completeness: float | None,
) -> float | None:
    """Composite scoring based on enterprise architecture:
    Retrieval confidence carries the highest weight in the composite score.
    (retrieval_conf * 0.50) + (coverage * 0.30) + (completeness * 0.20)
    """
    retrieval = retrieval_confidence if retrieval_confidence is not None else 0.0
    coverage = citation_coverage if citation_coverage is not None else 1.0
    comp = completeness if completeness is not None else 1.0
    
    composite = (retrieval * 0.50) + (coverage * 0.30) + (comp * 0.20)
    return float(round(composite, 4))


def unsupported_citation_markers(claims: list[ClaimVerification]) -> list[int]:
    """Citation marker numbers (e.g. the `1` in `[1]`) that appeared on at
    least one claim the judge flagged as unsupported."""
    markers: set[int] = set()
    for claim in claims:
        if claim.supported is False:
            markers.update(claim.citation_markers)
    return sorted(markers)
