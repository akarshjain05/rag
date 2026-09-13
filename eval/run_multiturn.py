import argparse
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag_api.core.settings import get_settings
from rag_api.adapters.vectorstore.embeddings import build_embedding_client
from rag_api.domain.generation.generation import AnswerGenerator
from rag_api.adapters.llm.llm_client import build_llm_client
from rag_api.services.query_condensation import condense_query
from rag_api.services.redis_conversation import Turn, ConversationStore

def main():
    with open("eval/multiturn_qa.json") as f:
        data = json.load(f)

    settings = get_settings()
    llm_client = build_llm_client(
        settings.llm_provider,
        model=settings.anthropic_model if settings.llm_provider == "anthropic" else settings.openai_llm_model,
        api_key=settings.anthropic_api_key if settings.llm_provider == "anthropic" else settings.openai_api_key,
        base_url=settings.openai_base_url if settings.llm_provider == "openai" else None,
    )
    
    if settings.llm_provider == "none":
        print("Skipping multiturn eval. Generative LLM provider is required to condense queries.")
        return

    for conv in data:
        print(f"\n--- Conversation: {conv['conversation_id']} ---")
        store = ConversationStore()
        cid = store.create_conversation()
        
        for i, turn in enumerate(conv["turns"]):
            question = turn["question"]
            history = store.get_history(cid)
            
            # 1. Test condensation
            condensed = condense_query(llm_client, question, history)
            print(f"T{i+1} User: {question}")
            print(f"T{i+1} Condensed: {condensed}")
            
            if "pronoun_resolution_target" in turn:
                # Basic strict string check for smoke testing
                if turn["pronoun_resolution_target"].lower() not in condensed.lower():
                    print(f"[FAIL] Did not resolve pronoun to '{turn['pronoun_resolution_target']}'")
                else:
                    print("[PASS] Pronoun successfully resolved.")
                    
            # Mock an assistant response for the next turn's history
            store.append_turn(cid, Turn(user=question, assistant="Mocked answer about " + condensed))

if __name__ == "__main__":
    main()
