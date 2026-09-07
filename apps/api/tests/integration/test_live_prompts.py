import pytest
import os
from rag_api.adapters.llm.openai_client import OpenAIClient
from rag_api.services.query_condensation import normalize_query

# Use a custom marker so this doesn't run during standard `pytest` runs
@pytest.mark.integration 
def test_live_normalizer_fixes_extreme_typos():
    """
    Actually hits the OpenAI/Anthropic API to verify the model's reasoning capabilities
    haven't degraded and that it respects the 'Output ONLY the string' rule.
    """
    # Pulls from .env (Assuming OPENAI_API_KEY is available)
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("No OPENAI_API_KEY found, skipping live integration test.")
        
    real_client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Provide a severely garbled technical query
    garbage_query = "hw do i rset my datbas passwrod on the prd env?"
    
    # Execute against the live model
    clean_query = normalize_query(garbage_query, llm_client=real_client)
    
    # Assertions evaluating the AI's actual intelligence
    clean_lower = clean_query.lower()
    
    # 1. Did it fix the spelling?
    assert "database" in clean_lower
    assert "password" in clean_lower
    assert "reset" in clean_lower
    
    # 2. Did it expand the acronym contextually?
    assert "prod" in clean_lower or "production" in clean_lower
    
    # 3. Did it obey the negative constraint? (No conversational filler)
    assert "here is" not in clean_lower
    assert "certainly" not in clean_lower
