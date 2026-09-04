from __future__ import annotations

from unittest.mock import MagicMock

from rag_api.domain.generation.generation import AnswerGenerator, _extract_and_validate_citations
from rag_api.domain.models import ClaimVerification, RetrievedChunk
from rag_api.domain.generation.verification import CitationVerifier, VerificationResult


def make_chunk(chunk_id, text, source_document="handbook.md", section_heading=None, page_number=None, dense_similarity=0.9):
    """dense_similarity defaults high (0.9) so ordinary tests exercise the
    normal generation path rather than tripping the low-confidence
    short-circuit (default threshold 0.3) by accident -- tests that want
    the low-confidence path set it explicitly and low."""
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        metadata={
            "source_document": source_document,
            "section_heading": section_heading or "",
            "page_number": page_number if page_number is not None else -1,
        },
        dense_similarity=dense_similarity,
    )


# --------------------------------------------------------------------------
# citation validation helper (structural: is [N] in range)
# --------------------------------------------------------------------------
def test_extract_and_validate_citations_all_valid():
    valid, invalid = _extract_and_validate_citations("Vacation accrues monthly [1]. Remote work needs approval [2].", num_sources=2)
    assert valid == [1, 2]
    assert invalid == []


def test_extract_and_validate_citations_flags_hallucinated_marker():
    valid, invalid = _extract_and_validate_citations("According to the docs [1] and also [5].", num_sources=2)
    assert valid == [1]
    assert invalid == [5]


def test_extract_and_validate_citations_no_markers():
    valid, invalid = _extract_and_validate_citations("A plain answer with no citations.", num_sources=3)
    assert valid == []
    assert invalid == []


# --------------------------------------------------------------------------
# no_context / low_confidence short-circuits
# --------------------------------------------------------------------------
def test_no_chunks_returns_no_context_result():
    generator = AnswerGenerator(llm_client=None, mode="extractive")
    result = generator.generate("What is the vacation policy?", [])
    assert result.mode == "no_context"
    assert result.sources == []
    assert result.retrieval_confidence == 0.0
    assert result.composite_confidence == 0.0


def test_low_confidence_chunks_skip_generation_entirely():
    fake_llm = MagicMock()
    weak_chunks = [make_chunk("a", "vaguely related text", dense_similarity=0.1)]
    generator = AnswerGenerator(llm_client=fake_llm, mode="llm", low_confidence_threshold=0.3)

    result = generator.generate("an unrelated question", weak_chunks)

    assert result.mode == "low_confidence"
    assert result.retrieval_confidence == 0.1
    fake_llm.generate.assert_not_called()  # the whole point: no wasted LLM call


def test_low_confidence_answer_names_the_weak_matches_and_a_next_step():
    weak_chunks = [make_chunk("a", "text", source_document="policies.md", dense_similarity=0.05)]
    generator = AnswerGenerator(llm_client=None, mode="extractive", low_confidence_threshold=0.3)

    result = generator.generate("question", weak_chunks)

    assert "policies.md" in result.answer
    assert result.sources  # what was found is still surfaced, not hidden
    assert result.sources[0]["source_document"] == "policies.md"


def test_low_confidence_threshold_none_disables_the_check():
    weak_chunks = [make_chunk("a", "Some content here.", dense_similarity=0.01)]
    generator = AnswerGenerator(llm_client=None, mode="extractive", low_confidence_threshold=None)

    result = generator.generate("question", weak_chunks)

    assert result.mode == "extractive"  # proceeded normally despite very low confidence


def test_default_low_confidence_threshold_is_0_3():
    generator = AnswerGenerator(llm_client=None, mode="extractive")
    assert generator.low_confidence_threshold == 0.3


# --------------------------------------------------------------------------
# Extractive mode
# --------------------------------------------------------------------------
def test_extractive_mode_returns_top_chunk_with_citation():
    chunks = [make_chunk("a", "Vacation accrues at 1.5 days per month."), make_chunk("b", "Remote work needs approval.")]
    generator = AnswerGenerator(llm_client=None, mode="extractive")

    result = generator.generate("vacation policy?", chunks)

    assert result.mode == "extractive"
    assert "Vacation accrues at 1.5 days per month." in result.answer
    assert "[1]" in result.answer
    assert result.used_citation_markers == [1]
    assert result.invalid_citation_markers == []
    assert result.sources[0]["marker"] == 1
    assert result.sources[0]["source_document"] == "handbook.md"


def test_extractive_mode_citation_coverage_is_trivially_full():
    chunks = [make_chunk("a", "Some multi-sentence chunk. It has two sentences.")]
    result = AnswerGenerator(llm_client=None, mode="extractive").generate("q", chunks)

    assert result.citation_coverage == 1.0
    assert result.citation_coverage_basis == "extractive"
    assert result.completeness is None  # no judge ran to assess it


def test_extractive_mode_retrieval_confidence_reflects_chunk_similarity():
    chunks = [make_chunk("a", "text", dense_similarity=0.85)]
    result = AnswerGenerator(llm_client=None, mode="extractive").generate("q", chunks)
    assert result.retrieval_confidence == 0.85


# --------------------------------------------------------------------------
# LLM mode: prompt construction + structural citation validation
# --------------------------------------------------------------------------
def test_llm_mode_builds_context_with_citation_markers_and_source_metadata():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "Vacation accrues monthly [1]."
    chunks = [
        make_chunk("a", "Vacation accrues at 1.5 days per month.", section_heading="Vacation Policy"),
        make_chunk("b", "Remote work needs manager approval.", page_number=3),
    ]
    generator = AnswerGenerator(llm_client=fake_llm, mode="llm")

    result = generator.generate("what is the vacation policy?", chunks)

    assert result.mode == "llm"
    assert result.answer == "Vacation accrues monthly [1]."
    assert result.used_citation_markers == [1]
    assert result.invalid_citation_markers == []

    system_arg, user_arg = fake_llm.generate.call_args[0]
    assert "[1]" in user_arg and "[2]" in user_arg
    assert "Vacation Policy" in user_arg
    assert "page 3" in user_arg
    assert "what is the vacation policy?" in user_arg


def test_llm_mode_flags_hallucinated_citation_without_dropping_answer():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "This is covered in excerpt [7]."  # only 1 excerpt provided
    chunks = [make_chunk("a", "Some real content.")]
    generator = AnswerGenerator(llm_client=fake_llm, mode="llm")

    result = generator.generate("question", chunks)

    assert result.answer == "This is covered in excerpt [7]."  # answer is still returned
    assert result.invalid_citation_markers == [7]  # but flagged as unverifiable
    assert result.used_citation_markers == []


# --------------------------------------------------------------------------
# LLM mode without a citation verifier: structural coverage only
# --------------------------------------------------------------------------
def test_llm_mode_without_verifier_uses_structural_coverage_basis():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "Cited claim [1]. Uncited claim with no marker at all."
    chunks = [make_chunk("a", "some excerpt")]
    generator = AnswerGenerator(llm_client=fake_llm, mode="llm")  # no citation_verifier

    result = generator.generate("q", chunks)

    assert result.citation_coverage_basis == "structural"
    assert result.citation_coverage == 0.5  # 1 of 2 sentences has a citation
    assert result.completeness is None
    assert result.unsupported_citation_markers == []  # nothing to flag without a judge


# --------------------------------------------------------------------------
# LLM mode with a citation verifier: verified coverage + unsupported flags
# --------------------------------------------------------------------------
def test_llm_mode_with_verifier_uses_verified_coverage_and_flags_unsupported():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "Supported claim [1]. Unsupported claim [2]."
    fake_verifier = MagicMock(spec=CitationVerifier)
    fake_verifier.verify.return_value = VerificationResult(
        claims=[
            ClaimVerification(claim_text="Supported claim [1].", citation_markers=[1], supported=True),
            ClaimVerification(claim_text="Unsupported claim [2].", citation_markers=[2], supported=False),
        ],
        completeness=0.7,
    )
    chunks = [make_chunk("a", "excerpt one"), make_chunk("b", "excerpt two")]
    generator = AnswerGenerator(llm_client=fake_llm, mode="llm", citation_verifier=fake_verifier)

    result = generator.generate("q", chunks)

    fake_verifier.verify.assert_called_once_with("q", "Supported claim [1]. Unsupported claim [2].", chunks)
    assert result.citation_coverage_basis == "verified"
    assert result.citation_coverage == 0.5
    assert result.completeness == 0.7
    assert result.unsupported_citation_markers == [2]


def test_llm_mode_composite_confidence_averages_the_three_subscores():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "Answer [1]."
    fake_verifier = MagicMock(spec=CitationVerifier)
    fake_verifier.verify.return_value = VerificationResult(
        claims=[ClaimVerification(claim_text="Answer [1].", citation_markers=[1], supported=True)],
        completeness=0.6,
    )
    chunks = [make_chunk("a", "excerpt", dense_similarity=0.9)]
    generator = AnswerGenerator(llm_client=fake_llm, mode="llm", citation_verifier=fake_verifier)

    result = generator.generate("q", chunks)

    # retrieval_confidence=0.9, citation_coverage=1.0 (the one claim is supported), completeness=0.6
    assert result.retrieval_confidence == 0.9
    assert result.citation_coverage == 1.0
    assert result.composite_confidence == (0.9 + 1.0 + 0.6) / 3
