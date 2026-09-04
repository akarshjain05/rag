from __future__ import annotations

import pytest

from rag_api.domain.generation.confidence import (
    compute_citation_coverage,
    compute_composite_confidence,
    compute_retrieval_confidence,
    unsupported_citation_markers,
)
from rag_api.domain.models import ClaimVerification, RetrievedChunk


def make_chunk(dense_similarity):
    return RetrievedChunk(chunk_id="x", text="t", metadata={}, dense_similarity=dense_similarity)


# --------------------------------------------------------------------------
# compute_retrieval_confidence
# --------------------------------------------------------------------------
def test_retrieval_confidence_averages_dense_similarity():
    chunks = [make_chunk(0.9), make_chunk(0.7)]
    assert compute_retrieval_confidence(chunks) == 0.8


def test_retrieval_confidence_sparse_only_chunk_contributes_zero():
    chunks = [make_chunk(0.8), make_chunk(None)]  # second chunk: sparse-only hit
    assert compute_retrieval_confidence(chunks) == 0.4


def test_retrieval_confidence_no_chunks_is_zero():
    assert compute_retrieval_confidence([]) == 0.0


def test_retrieval_confidence_clamped_to_valid_range():
    assert compute_retrieval_confidence([make_chunk(1.5)]) == 1.0
    assert compute_retrieval_confidence([make_chunk(-0.5)]) == 0.0


# --------------------------------------------------------------------------
# compute_citation_coverage
# --------------------------------------------------------------------------
def test_citation_coverage_no_claims_is_vacuously_full():
    coverage, basis = compute_citation_coverage([])
    assert coverage == 1.0
    assert basis == "structural"


def test_citation_coverage_verified_basis_when_verification_ran():
    claims = [
        ClaimVerification(claim_text="a", citation_markers=[1], supported=True),
        ClaimVerification(claim_text="b", citation_markers=[2], supported=False),
    ]
    coverage, basis = compute_citation_coverage(claims)
    assert coverage == 0.5
    assert basis == "verified"


def test_citation_coverage_structural_basis_when_verification_did_not_run():
    claims = [
        ClaimVerification(claim_text="a", citation_markers=[1], supported=None),
        ClaimVerification(claim_text="b", citation_markers=[], supported=None),
    ]
    coverage, basis = compute_citation_coverage(claims)
    assert coverage == 0.5
    assert basis == "structural"


def test_citation_coverage_mixed_verified_and_unverified_claims_uses_verified_basis():
    # one claim was verified (e.g. it had a citation), one had none to verify at all
    claims = [
        ClaimVerification(claim_text="a", citation_markers=[1], supported=True),
        ClaimVerification(claim_text="b", citation_markers=[], supported=None),
    ]
    coverage, basis = compute_citation_coverage(claims)
    assert basis == "verified"
    assert coverage == 0.5  # only claim "a" counts as good


# --------------------------------------------------------------------------
# compute_composite_confidence
# --------------------------------------------------------------------------
def test_composite_confidence_averages_available_scores():
    assert compute_composite_confidence(0.8, 0.6, 1.0) == pytest.approx(0.8)


def test_composite_confidence_ignores_missing_scores_rather_than_zeroing_them():
    assert compute_composite_confidence(0.9, None, None) == 0.9


def test_composite_confidence_none_when_nothing_available():
    assert compute_composite_confidence(None, None, None) is None


# --------------------------------------------------------------------------
# unsupported_citation_markers
# --------------------------------------------------------------------------
def test_unsupported_citation_markers_collects_only_flagged_false():
    claims = [
        ClaimVerification(claim_text="a", citation_markers=[1], supported=True),
        ClaimVerification(claim_text="b", citation_markers=[2, 3], supported=False),
        ClaimVerification(claim_text="c", citation_markers=[4], supported=None),
    ]
    assert unsupported_citation_markers(claims) == [2, 3]


def test_unsupported_citation_markers_empty_when_all_supported_or_unverified():
    claims = [
        ClaimVerification(claim_text="a", citation_markers=[1], supported=True),
        ClaimVerification(claim_text="b", citation_markers=[2], supported=None),
    ]
    assert unsupported_citation_markers(claims) == []
