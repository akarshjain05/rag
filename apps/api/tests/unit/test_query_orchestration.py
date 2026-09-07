import pytest
from unittest.mock import MagicMock

# Importing from our actual application modules
from rag_api.services.query_condensation import normalize_query, expand_query

@pytest.fixture
def mock_llm_client():
    """Provides a mocked LLM client to prevent live API calls during CI."""
    client = MagicMock()
    # Mock the synchronous generate method
    client.generate = MagicMock()
    return client

def test_proactive_normalizer_prompt_construction(mock_llm_client):
    """
    Tests that the Normalizer strictly commands the LLM to fix spelling
    and does NOT ask for concept expansion.
    """
    # 1. Setup
    raw_query = "what is wtaermakring?"
    mock_llm_client.generate.return_value = "what is watermarking"

    # 2. Execute
    result = normalize_query(raw_query, llm_client=mock_llm_client)

    # 3. Assert Response Handling
    assert result == "what is watermarking"

    # 4. Assert Strict Prompt Compliance (Guards against Prompt Drift)
    mock_llm_client.generate.assert_called_once()
    call_args = mock_llm_client.generate.call_args[0]
    prompt_used = call_args[0]
    
    assert "spelling" in prompt_used.lower(), "Normalizer prompt MUST contain spelling instructions."
    assert "synonym" in prompt_used.lower() and "do not add synonyms" in prompt_used.lower(), "Normalizer must NOT expand concepts."
    assert raw_query in call_args[1], "The raw query was not passed to the LLM."

def test_reactive_crag_expansion_prompt_construction(mock_llm_client):
    """
    Tests that the CRAG fallback strictly commands the LLM to generate synonyms
    and technical terms after a clean query fails retrieval.
    """
    # 1. Setup
    clean_query = "watermarking"
    mock_llm_client.generate.return_value = "digital watermarking, DRM, steganography, data hiding"

    # 2. Execute
    result = expand_query(clean_query, llm_client=mock_llm_client)

    # 3. Assert Response Handling
    assert "DRM" in result

    # 4. Assert Strict Prompt Compliance
    mock_llm_client.generate.assert_called_once()
    call_args = mock_llm_client.generate.call_args[0]
    prompt_used = call_args[0]
    
    assert "synonyms" in prompt_used.lower(), "CRAG prompt MUST instruct the LLM to generate synonyms."
    assert "technical terms" in prompt_used.lower(), "CRAG prompt MUST ask for domain-specific terms."
    assert clean_query in call_args[1], "The clean query was not passed to the CRAG LLM."
