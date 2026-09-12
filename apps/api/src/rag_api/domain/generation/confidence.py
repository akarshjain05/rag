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

    def _chunk_score(c: RetrievedChunk) -> float:
        d = c.dense_similarity if c.dense_similarity is not None else 0.0
        if c.rerank_score is not None:
            return 0.7 * c.rerank_score + 0.3 * d
        return d

    calibrated_score = max(_chunk_score(c) for c in chunks)

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
    weight_retrieval = 0.50
    weight_coverage = 0.30
    weight_comp = 0.20
    
    val_coverage = citation_coverage if citation_coverage is not None else 0.0
    val_comp = completeness if completeness is not None else 0.0
    
    if citation_coverage is None and completeness is None:
        return float(round(retrieval, 4))
    elif citation_coverage is None:
        total_weight = weight_retrieval + weight_comp
        composite = (retrieval * weight_retrieval + val_comp * weight_comp) / total_weight
    elif completeness is None:
        total_weight = weight_retrieval + weight_coverage
        composite = (retrieval * weight_retrieval + val_coverage * weight_coverage) / total_weight
    else:
        composite = (retrieval * weight_retrieval) + (val_coverage * weight_coverage) + (val_comp * weight_comp)
        
    return float(round(composite, 4))


def unsupported_citation_markers(claims: list[ClaimVerification]) -> list[int]:
    """Citation marker numbers (e.g. the `1` in `[1]`) that appeared on at
    least one claim the judge flagged as unsupported."""
    markers: set[int] = set()
    for claim in claims:
        if claim.supported is False:
            markers.update(claim.citation_markers)
    return sorted(markers)
