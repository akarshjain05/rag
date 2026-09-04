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
