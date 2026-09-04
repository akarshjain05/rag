from __future__ import annotations

from unittest.mock import MagicMock

from rag_api.domain.models import RetrievedChunk
from rag_api.domain.generation.verification import CitationVerifier, split_into_claims


def make_chunk(chunk_id, text):
    return RetrievedChunk(chunk_id=chunk_id, text=text, metadata={"source_document": "doc.md"})


# --------------------------------------------------------------------------
# split_into_claims
# --------------------------------------------------------------------------
def test_split_into_claims_extracts_markers_per_sentence():
    claims = split_into_claims("Vacation accrues monthly [1]. Remote work needs approval [2].")
    assert [c.claim_text for c in claims] == ["Vacation accrues monthly [1].", "Remote work needs approval [2]."]
    assert claims[0].citation_markers == [1]
    assert claims[1].citation_markers == [2]


def test_split_into_claims_handles_multiple_markers_on_one_sentence():
    claims = split_into_claims("This is covered by both policies [1][2].")
    assert claims[0].citation_markers == [1, 2]


def test_split_into_claims_uncited_sentence_has_no_markers():
    claims = split_into_claims("This sentence has no citation at all.")
    assert claims[0].citation_markers == []


def test_split_into_claims_empty_answer_returns_no_claims():
    assert split_into_claims("") == []


# --------------------------------------------------------------------------
# CitationVerifier
# --------------------------------------------------------------------------
def test_verify_marks_supported_and_unsupported_claims():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"claims": {"1": true, "2": false}, "completeness": 0.9}'
    chunks = [make_chunk("a", "Employees accrue 1.5 vacation days per month."), make_chunk("b", "Lunch is provided on Fridays.")]

    verifier = CitationVerifier(fake_llm)
    result = verifier.verify(
        "what is the vacation policy",
        "Vacation accrues at 1.5 days per month [1]. The office has free snacks [2].",
        chunks,
    )

    assert result.claims[0].supported is True
    assert result.claims[1].supported is False
    assert result.completeness == 0.9


def test_verify_sends_actual_excerpt_text_for_each_cited_marker():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"claims": {"1": true}, "completeness": 1.0}'
    chunks = [make_chunk("a", "Employees accrue 1.5 vacation days per month.")]

    CitationVerifier(fake_llm).verify("q", "Vacation accrues monthly [1].", chunks)

    system_arg, user_arg = fake_llm.generate.call_args[0]
    assert "Employees accrue 1.5 vacation days per month." in user_arg
    assert "Vacation accrues monthly [1]." in user_arg
    assert "JSON" in system_arg


def test_verify_single_call_regardless_of_claim_count():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "{}"
    answer = " ".join(f"Claim number {i} here [1]." for i in range(10))

    CitationVerifier(fake_llm).verify("q", answer, [make_chunk("a", "excerpt")])

    assert fake_llm.generate.call_count == 1


def test_verify_uncited_claim_is_never_marked_supported():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"claims": {"1": true}, "completeness": 0.5}'
    chunks = [make_chunk("a", "some excerpt")]

    result = CitationVerifier(fake_llm).verify("q", "A cited claim [1]. An uncited claim with no marker.", chunks)

    cited, uncited = result.claims[0], result.claims[1]
    assert cited.supported is True
    assert uncited.citation_markers == []
    assert uncited.supported is None  # never sent for verification -- nothing to check


def test_verify_no_citations_at_all_still_scores_completeness():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"completeness": 0.3}'

    result = CitationVerifier(fake_llm).verify("q", "An answer with no citations whatsoever.", [make_chunk("a", "x")])

    assert result.completeness == 0.3
    assert all(c.supported is None for c in result.claims)


def test_verify_malformed_response_degrades_to_none_supported_and_none_completeness():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "I cannot verify this in JSON format, sorry."
    chunks = [make_chunk("a", "excerpt")]

    result = CitationVerifier(fake_llm).verify("q", "A claim [1].", chunks)

    assert result.claims[0].supported is None  # not "unsupported" -- genuinely unknown
    assert result.completeness is None


def test_verify_out_of_range_citation_marker_gets_placeholder_excerpt_text():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"claims": {"1": false}, "completeness": 0.5}'

    CitationVerifier(fake_llm).verify("q", "A claim citing something nonexistent [9].", [make_chunk("a", "only excerpt")])

    _, user_arg = fake_llm.generate.call_args[0]
    assert "out of range" in user_arg


def test_verify_completeness_score_is_clamped_to_valid_range():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"claims": {"1": true}, "completeness": 5.0}'  # out of [0,1] range

    result = CitationVerifier(fake_llm).verify("q", "A claim [1].", [make_chunk("a", "excerpt")])

    assert result.completeness == 1.0  # clamped, not passed through raw


def test_verify_invalid_json_syntax_falls_back_gracefully():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "{this is not valid json}"

    result = CitationVerifier(fake_llm).verify("q", "A claim [1].", [make_chunk("a", "excerpt")])

    assert result.claims[0].supported is None
    assert result.completeness is None


def test_verify_non_numeric_completeness_is_ignored_not_fatal():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"claims": {"1": true}, "completeness": "very high"}'

    result = CitationVerifier(fake_llm).verify("q", "A claim [1].", [make_chunk("a", "excerpt")])

    assert result.claims[0].supported is True  # the parseable part still works
    assert result.completeness is None  # the unparseable part degrades safely


def test_verify_non_string_key_in_claims_object_is_skipped():
    fake_llm = MagicMock()
    # "claims" as a list instead of the expected {"1": true} object shape
    fake_llm.generate.return_value = '{"claims": [1, 2, 3], "completeness": 0.5}'

    result = CitationVerifier(fake_llm).verify("q", "A claim [1].", [make_chunk("a", "excerpt")])

    assert result.claims[0].supported is None  # malformed shape -> nothing marked, not a crash
    assert result.completeness == 0.5  # the sibling field still parses fine


def test_verify_non_numeric_claim_key_is_skipped_not_fatal():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"claims": {"abc": true}, "completeness": 0.5}'  # "abc" isn't an int

    result = CitationVerifier(fake_llm).verify("q", "A claim [1].", [make_chunk("a", "excerpt")])

    assert result.claims[0].supported is None  # unparseable key -> skipped, not a crash
    assert result.completeness == 0.5
