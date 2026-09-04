from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import numpy as np
import pytest

from rag_api.domain.models import RetrievedChunk
from rag_api.domain.retrieval.reranker import CrossEncoderReranker, LLMJudgeReranker, build_reranker


def make_chunk(chunk_id, text):
    return RetrievedChunk(chunk_id=chunk_id, text=text, metadata={"source_document": "doc.md"})


# --------------------------------------------------------------------------
# CrossEncoderReranker
# --------------------------------------------------------------------------
def test_cross_encoder_reranker_reorders_by_score(monkeypatch):
    """sentence-transformers (and torch) are a large optional dependency not
    installed in this environment; the wrapper's own logic -- calling
    .predict() correctly and reordering by score -- is verified by injecting
    a fake sentence_transformers module, the same pattern used for
    LocalEmbeddingClient."""
    fake_model = MagicMock()
    fake_model.predict.return_value = np.array([0.1, 0.9, 0.5])  # candidate b should win

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.CrossEncoder = MagicMock(return_value=fake_model)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    reranker = CrossEncoderReranker(model_name="fake/cross-encoder")
    candidates = [make_chunk("a", "text a"), make_chunk("b", "text b"), make_chunk("c", "text c")]

    result = reranker.rerank("some query", candidates, top_k=2)

    assert [c.chunk_id for c in result] == ["b", "c"]
    assert result[0].rerank_score == pytest.approx(0.9)
    fake_model.predict.assert_called_once_with([("some query", "text a"), ("some query", "text b"), ("some query", "text c")])


def test_cross_encoder_reranker_empty_candidates_returns_empty(monkeypatch):
    fake_module = types.ModuleType("sentence_transformers")
    fake_module.CrossEncoder = MagicMock(return_value=MagicMock())
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    reranker = CrossEncoderReranker()
    assert reranker.rerank("query", [], top_k=5) == []


# --------------------------------------------------------------------------
# LLMJudgeReranker
# --------------------------------------------------------------------------
def test_llm_judge_reranker_reorders_by_parsed_scores():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"1": 2, "2": 9, "3": 5}'
    candidates = [make_chunk("a", "text a"), make_chunk("b", "text b"), make_chunk("c", "text c")]

    reranker = LLMJudgeReranker(fake_llm)
    result = reranker.rerank("query", candidates, top_k=2)

    assert [c.chunk_id for c in result] == ["b", "c"]
    assert result[0].rerank_score == 9.0

    system_arg, user_arg = fake_llm.generate.call_args[0]
    assert "[1] text a" in user_arg
    assert "[2] text b" in user_arg
    assert "query" in user_arg
    assert "JSON" in system_arg


def test_llm_judge_reranker_single_call_regardless_of_candidate_count():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "{}"
    candidates = [make_chunk(str(i), f"text {i}") for i in range(20)]

    LLMJudgeReranker(fake_llm).rerank("query", candidates, top_k=5)

    assert fake_llm.generate.call_count == 1


def test_llm_judge_reranker_malformed_response_falls_back_to_original_order():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "Sure, here are some thoughts with no JSON at all."
    candidates = [make_chunk("a", "text a"), make_chunk("b", "text b")]

    result = LLMJudgeReranker(fake_llm).rerank("query", candidates, top_k=2)

    assert [c.chunk_id for c in result] == ["a", "b"]  # stable sort on all-zero scores == original order


def test_llm_judge_reranker_partial_response_scores_unparsed_as_zero():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"2": 7}'  # only scores candidate 2
    candidates = [make_chunk("a", "text a"), make_chunk("b", "text b"), make_chunk("c", "text c")]

    result = LLMJudgeReranker(fake_llm).rerank("query", candidates, top_k=3)

    assert result[0].chunk_id == "b"
    assert result[0].rerank_score == 7.0
    assert {c.chunk_id for c in result[1:]} == {"a", "c"}


def test_llm_judge_reranker_ignores_out_of_range_indices():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"1": 5, "99": 10}'  # index 99 doesn't exist
    candidates = [make_chunk("a", "text a")]

    result = LLMJudgeReranker(fake_llm).rerank("query", candidates, top_k=1)

    assert result[0].rerank_score == 5.0


def test_llm_judge_reranker_invalid_json_syntax_falls_back_to_zero_scores():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "{this is not valid json at all}"
    candidates = [make_chunk("a", "text a"), make_chunk("b", "text b")]

    result = LLMJudgeReranker(fake_llm).rerank("query", candidates, top_k=2)

    assert [c.chunk_id for c in result] == ["a", "b"]  # falls back to original order
    assert all(c.rerank_score == 0.0 for c in result)


def test_llm_judge_reranker_non_dict_json_falls_back_to_zero_scores():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "[1, 2, 3]"  # valid JSON, but not the expected object shape
    candidates = [make_chunk("a", "text a")]

    result = LLMJudgeReranker(fake_llm).rerank("query", candidates, top_k=1)

    assert result[0].rerank_score == 0.0


def test_llm_judge_reranker_non_numeric_score_value_is_skipped_not_fatal():
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"1": "very relevant", "2": 8}'  # "1"'s value isn't a number
    candidates = [make_chunk("a", "text a"), make_chunk("b", "text b")]

    result = LLMJudgeReranker(fake_llm).rerank("query", candidates, top_k=2)

    assert result[0].chunk_id == "b"  # the one parseable score still wins
    assert result[0].rerank_score == 8.0
    assert result[1].rerank_score == 0.0  # unparseable value -> safe default, not a crash


def test_llm_judge_reranker_empty_candidates_returns_empty():
    fake_llm = MagicMock()
    assert LLMJudgeReranker(fake_llm).rerank("query", [], top_k=5) == []
    fake_llm.generate.assert_not_called()


# --------------------------------------------------------------------------
# build_reranker factory
# --------------------------------------------------------------------------
def test_build_reranker_none_returns_none():
    assert build_reranker("none") is None


def test_build_reranker_llm_judge_requires_llm_client():
    with pytest.raises(ValueError, match="requires an LLM client"):
        build_reranker("llm_judge", llm_client=None)


def test_build_reranker_llm_judge_with_client_succeeds():
    fake_llm = MagicMock()
    reranker = build_reranker("llm_judge", llm_client=fake_llm)
    assert isinstance(reranker, LLMJudgeReranker)


def test_build_reranker_cross_encoder_succeeds(monkeypatch):
    fake_module = types.ModuleType("sentence_transformers")
    fake_module.CrossEncoder = MagicMock(return_value=MagicMock())
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    reranker = build_reranker("cross_encoder", model_name="fake/model")

    assert isinstance(reranker, CrossEncoderReranker)
    fake_module.CrossEncoder.assert_called_once_with("fake/model")


def test_build_reranker_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown reranker provider"):
        build_reranker("not-a-real-provider")
