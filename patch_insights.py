with open("apps/api/src/rag_api/services/redis_conversation.py", "r") as f:
    text = f.read()

target = """    def record_feedback(self, conversation_id: str, feedback: str):"""
replacement = """    def get_global_metrics(self) -> dict:
        total = int(self._client.get("metrics:total_queries") or 0)
        conf_sum = float(self._client.get("metrics:confidence_sum") or 0.0)
        up = int(self._client.get("metrics:thumbs_up") or 0)
        down = int(self._client.get("metrics:thumbs_down") or 0)
        avg_conf = (conf_sum / total) if total > 0 else 0.0
        return {
            "total_queries": total,
            "average_confidence": round(avg_conf, 2),
            "thumbs_up": up,
            "thumbs_down": down
        }

    def record_feedback(self, conversation_id: str, feedback: str):"""

text = text.replace(target, replacement)
with open("apps/api/src/rag_api/services/redis_conversation.py", "w") as f:
    f.write(text)


with open("apps/api/src/rag_api/services/conversation.py", "r") as f:
    text = f.read()

target2 = """    def record_feedback(self, conversation_id: str, feedback: str):"""
replacement2 = """    def get_global_metrics(self) -> dict:
        return {
            "total_queries": 0,
            "average_confidence": 0.0,
            "thumbs_up": 0,
            "thumbs_down": 0
        }

    def record_feedback(self, conversation_id: str, feedback: str):"""

text = text.replace(target2, replacement2)
with open("apps/api/src/rag_api/services/conversation.py", "w") as f:
    f.write(text)


with open("apps/api/src/rag_api/api/v1/insights.py", "r") as f:
    text = f.read()

target3 = """    # Fallback for in-memory store
    if not isinstance(store, RedisConversationStore):
        return {
            "total_queries": 0,
            "average_confidence": 0.0,
            "thumbs_up": 0,
            "thumbs_down": 0
        }
        
    client = store._client
    total = int(client.get("metrics:total_queries") or 0)
    conf_sum = float(client.get("metrics:confidence_sum") or 0.0)
    up = int(client.get("metrics:thumbs_up") or 0)
    down = int(client.get("metrics:thumbs_down") or 0)
    
    avg_conf = (conf_sum / total) if total > 0 else 0.0
    
    return {
        "total_queries": total,
        "average_confidence": round(avg_conf, 2),
        "thumbs_up": up,
        "thumbs_down": down
    }"""

replacement3 = """    return store.get_global_metrics()"""
text = text.replace(target3, replacement3)
with open("apps/api/src/rag_api/api/v1/insights.py", "w") as f:
    f.write(text)

