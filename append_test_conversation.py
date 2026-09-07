with open("apps/api/tests/unit/test_conversation.py", "a") as f:
    f.write("""

from rag_api.services.query_condensation import normalize_query, expand_query, should_expand_query

def test_normalize_query_fixes_typo():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "watermarking"
    result = normalize_query("wtaermakring", mock_llm)
    assert result == "watermarking"
    system_arg, user_arg = mock_llm.generate.call_args[0]
    assert "spelling" in system_arg.lower() or "typing" in system_arg.lower()
    assert user_arg == "wtaermakring"

def test_normalize_query_leaves_clean_query_unchanged():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "what is watermarking?"
    assert normalize_query("what is watermarking?", mock_llm) == "what is watermarking?"

def test_normalize_query_strips_whitespace():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "  watermarking  \\n"
    assert normalize_query("wtaermakring", mock_llm) == "watermarking"

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
""")
