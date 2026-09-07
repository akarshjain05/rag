from rag_api.adapters.llm.llm_client import LLMClient

class QueryRewriter:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def rewrite(self, raw_query: str) -> str:
        """Fixes typos and normalizes intent before retrieval."""
        system_prompt = (
            "You are a search query normalizer. "
            "Correct any spelling mistakes and clarify the intent of the following search query. "
            "Output ONLY the corrected query text, with no conversational filler, preamble, or quotes."
        )
        
        # Use the provided LLM client
        clean_query = self.llm.generate(
            system=system_prompt,
            user=raw_query
        )
        
        # Strip quotes just in case the LLM adds them
        return clean_query.strip().strip('"').strip("'")
