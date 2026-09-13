import os

# 1. Update retrieval.py
with open("apps/api/src/rag_api/domain/retrieval/retrieval.py", "r") as f:
    text = f.read()

text = text.replace("original_query: str | None = None,", "rerank_query: str | None = None,")
text = text.replace("if original_query and self.reranker:", "if rerank_query and self.reranker:")
text = text.replace("return self.reranker.rerank(original_query, rrf_results, top_k)", "return self.reranker.rerank(rerank_query, rrf_results, top_k)")

with open("apps/api/src/rag_api/domain/retrieval/retrieval.py", "w") as f:
    f.write(text)

# 2. Update query_orchestration.py
with open("apps/api/src/rag_api/services/query_orchestration.py", "r") as f:
    text = f.read()

text = text.replace("original_query=search_query,", "rerank_query=search_query,")

with open("apps/api/src/rag_api/services/query_orchestration.py", "w") as f:
    f.write(text)

