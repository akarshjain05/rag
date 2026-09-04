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
    """Mean dense cosine similarity across the returned chunks. A chunk
    found only via sparse search (no dense_similarity) contributes 0.0 --
    dense search considering it irrelevant is itself a meaningful low
    signal, not a gap to paper over with a neutral default."""
    if not chunks:
        return 0.0
    values = [c.dense_similarity if c.dense_similarity is not None else 0.0 for c in chunks]
    return max(0.0, min(1.0, sum(values) / len(values)))


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
    """Equal-weighted mean of whichever sub-scores are available. None only
    when none of the three could be computed at all."""
    values = [v for v in (retrieval_confidence, citation_coverage, completeness) if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def unsupported_citation_markers(claims: list[ClaimVerification]) -> list[int]:
    """Citation marker numbers (e.g. the `1` in `[1]`) that appeared on at
    least one claim the judge flagged as unsupported."""
    markers: set[int] = set()
    for claim in claims:
        if claim.supported is False:
            markers.update(claim.citation_markers)
    return sorted(markers)
