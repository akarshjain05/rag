import pytest
from unittest.mock import MagicMock
from rag_api.services.conversation import ConversationStore, Turn
from rag_api.services.query_condensation import condense_query

def test_conversation_store():
    store = ConversationStore()
    cid = store.create_conversation()
    assert isinstance(cid, str)
    assert len(store.get_history(cid)) == 0
    
    store.append_turn(cid, Turn("hello", "hi there"))
    hist = store.get_history(cid)
    assert len(hist) == 1
    assert hist[0].user == "hello"
    assert hist[0].assistant == "hi there"

def test_condense_query_no_history():
    mock_llm = MagicMock()
    result = condense_query("what?", [], mock_llm)
    assert result == "what?"
    mock_llm.generate.assert_not_called()

def test_condense_query_with_history():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "What is the policy?"
    history = [Turn("What is the vacation policy?", "It is 15 days.")]
    
    result = condense_query("Does it carry over?", history, mock_llm)
    assert result == "What is the policy?"
    
    mock_llm.generate.assert_called_once()
    system_arg, user_arg = mock_llm.generate.call_args[0][:2]
    kwargs = mock_llm.generate.call_args[1]
    
    assert "rewrite the follow-up" in system_arg
    assert user_arg == "Does it carry over?"
    assert kwargs["history"] == [
        {"role": "user", "content": "What is the vacation policy?"},
        {"role": "assistant", "content": "It is 15 days."}
    ]


from rag_api.services.query_condensation import normalize_query, expand_query, should_expand_query

def test_normalize_query_fixes_typo():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"clean_query": "watermarking", "target_date": null}'
    result = normalize_query("wtaermakring", mock_llm)
    assert result.get("clean_query") == "watermarking"
    system_arg, user_arg = mock_llm.generate.call_args[0]
    assert "spelling" in system_arg.lower() or "typing" in system_arg.lower()
    assert user_arg == "wtaermakring"

def test_normalize_query_leaves_clean_query_unchanged():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"clean_query": "what is watermarking?", "target_date": null}'
    assert normalize_query("what is watermarking?", mock_llm).get("clean_query") == "what is watermarking?"

def test_normalize_query_strips_whitespace():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"clean_query": "watermarking", "target_date": null}'
    assert normalize_query("wtaermakring", mock_llm).get("clean_query") == "watermarking"

def test_should_expand_query_true_for_zero_score():
    assert should_expand_query(0.0) is True

def test_should_expand_query_true_for_mid_score():
    assert should_expand_query(0.5) is True

def test_should_expand_query_false_at_and_above_ceiling():
    assert should_expand_query(0.80) is False
    assert should_expand_query(0.95) is False

def test_should_expand_query_respects_custom_ceiling():
    assert should_expand_query(0.5, ceiling=0.4) is False

def test_expand_query_prompt_assumes_clean_spelling():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "expanded technical query"
    expand_query("watermarking", mock_llm)
    system_arg, _ = mock_llm.generate.call_args[0]
    assert "spell" in system_arg.lower()
    assert "assume" in system_arg.lower()

def test_mark_and_pop_interrupted_round_trips():
    store = ConversationStore()
    cid = store.create_conversation()
    store.mark_interrupted(cid, "What is the escalation process?")
    assert store.pop_interrupted(cid) == "What is the escalation process?"

def test_pop_interrupted_is_one_shot():
    store = ConversationStore()
    cid = store.create_conversation()
    store.mark_interrupted(cid, "some question")
    store.pop_interrupted(cid)
    assert store.pop_interrupted(cid) is None

def test_pop_interrupted_returns_none_when_nothing_marked():
    store = ConversationStore()
    cid = store.create_conversation()
    assert store.pop_interrupted(cid) is None
