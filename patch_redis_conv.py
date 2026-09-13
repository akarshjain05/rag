with open("apps/api/src/rag_api/services/redis_conversation.py", "r") as f:
    text = f.read()

target = """    def log_query_metrics(self, confidence: float) -> None:
        self._client.incr("metrics:total_queries")
        self._client.incrbyfloat("metrics:confidence_sum", confidence)"""

replacement = """    def log_query_metrics(self, confidence: float) -> None:
        self._client.incr("metrics:total_queries")
        self._client.incrbyfloat("metrics:confidence_sum", confidence)

    def get_global_metrics(self) -> dict:
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
        }"""

text = text.replace(target, replacement)
with open("apps/api/src/rag_api/services/redis_conversation.py", "w") as f:
    f.write(text)

