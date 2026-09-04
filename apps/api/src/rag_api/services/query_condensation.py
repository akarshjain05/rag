from rag_api.adapters.llm.llm_client import LLMClient
from rag_api.services.conversation import Turn

def condense_query(query: str, history: list[Turn], llm_client: LLMClient) -> str:
    if not history:
        return query
        
    system = (
        "Given the following conversation history and the user's latest follow-up question, "
        "rewrite the follow-up question to be a standalone query that can be understood "
        "without the conversation history. Do not answer the question, just rewrite it. "
        "If it is already standalone, return it exactly as is."
    )
    
    # Format history for the LLM
    llm_history = []
    for turn in history:
        llm_history.append({"role": "user", "content": turn.user})
        llm_history.append({"role": "assistant", "content": turn.assistant})
        
    standalone_query = llm_client.generate(system, query, history=llm_history)
    print(f"\n=== CONDENSED QUERY ===\n{standalone_query}\n")
    
    return standalone_query.strip()
