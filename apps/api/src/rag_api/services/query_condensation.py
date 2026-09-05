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

def expand_query(query: str, llm_client: LLMClient) -> str:
    system = (
        "You are an expert search query expander for a technical RAG system. "
        "The user's original query returned ambiguous or low-confidence results. "
        "Rewrite the query to include synonyms, expanded acronyms, and related technical terms "
        "that might appear in formal documentation to improve search recall. "
        "Return ONLY the rewritten query string, nothing else."
    )
    expanded_query = llm_client.generate(system, query)
    print(f"\n=== CRAG EXPANDED QUERY ===\nOriginal: {query}\nExpanded: {expanded_query}\n")
    return expanded_query.strip()

def generate_hyde(query: str, llm_client: LLMClient) -> str:
    system = (
        "You are an expert technical writer. The user is asking a question that will be used to search a vector database. "
        "Your task is to write a hypothetical passage that perfectly answers the user's question. "
        "Write it exactly as it might appear in a formal textbook, documentation, or technical paper. "
        "Do not include conversational filler like 'Here is a hypothetical document'. "
        "Just output the hypothetical paragraph directly."
    )
    hyde_doc = llm_client.generate(system, query)
    print(f"\n=== HyDE DOCUMENT ===\n{hyde_doc}\n")
    return hyde_doc.strip()
