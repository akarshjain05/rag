import os
import sys

with open("eval/run_ragas_eval.py", "r") as f:
    text = f.read()

text = text.replace('DEFAULT_DATASET = Path(__file__).parent / "golden_qa.json"', 'DEFAULT_DATASET = Path(__file__).parent / "vellumiq_qa.json"')
text = text.replace('DEFAULT_CORPUS = Path(__file__).parent / "golden_corpus"', 'DEFAULT_CORPUS = Path(__file__).parent / "vellumiq_corpus"')

target_eval_llm = """        eval_llm = ChatOpenAI(model=os.environ.get("OPENAI_LLM_MODEL", "gpt-3.5-turbo"))
        eval_embeddings = OpenAIEmbeddings(model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))"""

replacement_eval_llm = """        from langchain_openai import ChatOpenAI
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain.callbacks.manager import CallbackManager
        
        # Use Groq (or fallback) via OpenAI compatible endpoint, with high retry
        eval_llm = ChatOpenAI(
            model=os.environ.get("OPENAI_LLM_MODEL", "gpt-4o"),
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.environ.get("OPENAI_API_KEY", "dummy"),
            max_retries=10
        )
        
        # Use local embeddings since Groq doesn't have embeddings
        local_model = os.environ.get("LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        eval_embeddings = HuggingFaceEmbeddings(model_name=local_model)"""

text = text.replace(target_eval_llm, replacement_eval_llm)

with open("eval/run_ragas_eval.py", "w") as f:
    f.write(text)

