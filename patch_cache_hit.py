with open("apps/api/src/rag_api/services/query_orchestration.py", "r") as f:
    text = f.read()

target = """        if cached_payload:
            log.info("semantic_cache.hit", query=search_query)
            cached_sources = cached_payload.sources
            cid = payload.conversation_id or store.create_conversation()"""

replacement = """        if cached_payload:
            log.info("semantic_cache.hit", query=search_query)
            
            # Log the metric for cache hits to ensure total_queries doesn't undercount
            store.log_query_metrics(float(cached_payload.retrieval_confidence) if cached_payload.retrieval_confidence is not None else 0.0)
            
            cached_sources = cached_payload.sources
            cid = payload.conversation_id or store.create_conversation()"""

text = text.replace(target, replacement)
with open("apps/api/src/rag_api/services/query_orchestration.py", "w") as f:
    f.write(text)

