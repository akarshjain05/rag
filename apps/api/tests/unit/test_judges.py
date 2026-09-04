from __future__ import annotations

from unittest.mock import MagicMock

from rag_api.domain.models import RetrievedChunk
from eval.golden_dataset import GoldenExample
from eval.judges import AnswerCorrectnessJudge, FaithfulnessJudge, join_chunk_texts


def chunk(text, source_document="doc.md"):
    return RetrievedChunk(chunk_id="x", text=text, metadata={"source_document": source_document})


# --------------------------------------------------------------------------
# join_chunk_texts
# --------------------------------------------------------------------------
def test_join_chunk_texts_labels_each_chunk_by_source():
    result = join_chunk_texts([chunk("first text", "a.md"), chunk("second text", "b.md")])
    assert "(a.md) first text" in result
    assert "(b.md) second text" in result


# --------------------------------------------------------------------------
# AnswerCorrectnessJudge
# --------------------------------------------------------------------------
def test_correctness_lookup_question_uses_reference_answer_comparison():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"correct": true, "reasoning": "matches"}'
    example = GoldenExample(id="q1", question="How many vacation days?", golden_answer="1.5 per month.", category="lookup")

    result = AnswerCorrectnessJudge(fake_llm).judge(example, "Employees get 1.5 days per month.", mode="llm")

    assert result.correct is True
    assert result.reasoning == "matches"
    system_arg, user_arg = fake_llm.generate.call_args[0]
    assert "1.5 per month." in user_arg
    assert "Employees get 1.5 days per month." in user_arg


def test_correctness_flags_wrong_lookup_answer():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"correct": false, "reasoning": "wrong number"}'
    example = GoldenExample(id="q1", question="q", golden_answer="1.5 per month.", category="lookup")

    result = AnswerCorrectnessJudge(fake_llm).judge(example, "Employees get 3 days per month.", mode="llm")

    assert result.correct is False


def test_correctness_unanswerable_question_uses_decline_detection_prompt():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"correct": true, "reasoning": "appropriately declined"}'
    example = GoldenExample(id="u1", question="What's the parking policy?", golden_answer="NOT_IN_CORPUS", category="unanswerable")

    result = AnswerCorrectnessJudge(fake_llm).judge(example, "I don't have information about parking.", mode="low_confidence")

    assert result.correct is True
    system_arg, _ = fake_llm.generate.call_args[0]
    assert "could not answer" in system_arg


def test_correctness_unanswerable_question_flags_a_fabricated_answer():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"correct": false, "reasoning": "fabricated a parking policy that does not exist"}'
    example = GoldenExample(id="u1", question="What's the parking policy?", golden_answer="NOT_IN_CORPUS", category="unanswerable")

    result = AnswerCorrectnessJudge(fake_llm).judge(example, "Employees get 2 free parking spots.", mode="llm")

    assert result.correct is False


def test_correctness_ambiguous_question_uses_ambiguity_aware_prompt():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"correct": true, "reasoning": "surfaced the ambiguity"}'
    example = GoldenExample(id="a1", question="What is the vacation policy?", golden_answer="Could mean several things.", category="ambiguous")

    result = AnswerCorrectnessJudge(fake_llm).judge(example, "This could refer to accrual, carryover, or the request process.", mode="llm")

    assert result.correct is True
    system_arg, _ = fake_llm.generate.call_args[0]
    assert "ambiguous" in system_arg.lower()


def test_correctness_malformed_response_returns_none_not_a_crash():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "I cannot provide a JSON verdict."
    example = GoldenExample(id="q1", question="q", golden_answer="a", category="lookup")

    result = AnswerCorrectnessJudge(fake_llm).judge(example, "some answer", mode="llm")

    assert result.correct is None


def test_correctness_non_boolean_correct_field_returns_none():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"correct": "yes", "reasoning": "not a real bool"}'
    example = GoldenExample(id="q1", question="q", golden_answer="a", category="lookup")

    result = AnswerCorrectnessJudge(fake_llm).judge(example, "some answer", mode="llm")

    assert result.correct is None


# --------------------------------------------------------------------------
# FaithfulnessJudge
# --------------------------------------------------------------------------
def test_faithfulness_computes_grounded_fraction():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"grounded": {"1": true, "2": false}}'

    result = FaithfulnessJudge(fake_llm).judge("Grounded claim [1]. Hallucinated claim [2].", [chunk("real content")])

    assert result.grounded_fraction == 0.5
    assert result.claim_count == 2


def test_faithfulness_checks_uncited_claims_too_not_just_cited_ones():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"grounded": {"1": false}}'

    result = FaithfulnessJudge(fake_llm).judge("An uncited hallucinated claim with no marker at all.", [chunk("unrelated content")])

    assert result.grounded_fraction == 0.0  # caught even without a citation marker to key off of


def test_faithfulness_sends_full_context_not_just_cited_excerpts():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"grounded": {"1": true}}'
    chunks = [chunk("context about vacation", "vacation.md"), chunk("context about security", "security.md")]

    FaithfulnessJudge(fake_llm).judge("A claim [1].", chunks)

    _, user_arg = fake_llm.generate.call_args[0]
    assert "context about vacation" in user_arg
    assert "context about security" in user_arg  # both chunks present, not just the cited one


def test_faithfulness_no_claims_is_vacuously_fully_grounded():
    fake_llm = MagicMock()
    result = FaithfulnessJudge(fake_llm).judge("", [chunk("content")])
    assert result.grounded_fraction == 1.0
    assert result.claim_count == 0
    fake_llm.generate.assert_not_called()


def test_faithfulness_malformed_response_returns_none_not_a_crash():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "not json at all"

    result = FaithfulnessJudge(fake_llm).judge("A claim [1].", [chunk("content")])

    assert result.grounded_fraction is None
    assert result.claim_count == 1


def test_faithfulness_out_of_range_claim_index_is_ignored():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"grounded": {"1": true, "99": true}}'  # only 1 claim exists

    result = FaithfulnessJudge(fake_llm).judge("Only one claim here.", [chunk("content")])

    assert result.grounded_fraction == 1.0  # index 99 doesn't inflate the count


def test_faithfulness_invalid_json_syntax_returns_none_not_a_crash():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "{this is not valid json}"

    result = FaithfulnessJudge(fake_llm).judge("A claim.", [chunk("content")])

    assert result.grounded_fraction is None


def test_faithfulness_non_dict_grounded_field_returns_none():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"grounded": [true, false]}'  # wrong shape -- expected an object

    result = FaithfulnessJudge(fake_llm).judge("A claim.", [chunk("content")])

    assert result.grounded_fraction is None


def test_faithfulness_non_numeric_claim_key_is_skipped_not_fatal():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"grounded": {"abc": true, "1": true}}'

    result = FaithfulnessJudge(fake_llm).judge("A claim.", [chunk("content")])

    assert result.grounded_fraction == 1.0  # the unparseable key is skipped; the valid one still counts
