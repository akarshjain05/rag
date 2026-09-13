with open("apps/api/src/rag_api/services/conversation.py", "r") as f:
    text = f.read()

# 1. Init metrics
target_init = """    def __init__(self, max_size: int = 1000):
        self._conversations: Dict[str, List[Turn]] = {}
        self._metadata: OrderedDict[str, dict] = OrderedDict()
        self._interrupted: Dict[str, str] = {}
        self.max_size = max_size"""

replacement_init = """    def __init__(self, max_size: int = 1000):
        self._conversations: Dict[str, List[Turn]] = {}
        self._metadata: OrderedDict[str, dict] = OrderedDict()
        self._interrupted: Dict[str, str] = {}
        self.max_size = max_size
        self._total_queries = 0
        self._confidence_sum = 0.0
        self._thumbs_up = 0
        self._thumbs_down = 0"""

text = text.replace(target_init, replacement_init)

# 2. Add get_global_metrics and update log_query_metrics and update_turn_feedback
target_log = """    def update_turn_feedback(self, conversation_id: str, turn_index: int, is_positive: bool | None) -> None:
        if conversation_id in self._conversations:
            if 0 <= turn_index < len(self._conversations[conversation_id]):
                self._conversations[conversation_id][turn_index].is_positive = is_positive

    def log_query_metrics(self, confidence: float) -> None:
        pass"""

replacement_log = """    def update_turn_feedback(self, conversation_id: str, turn_index: int, is_positive: bool | None) -> None:
        if conversation_id in self._conversations:
            if 0 <= turn_index < len(self._conversations[conversation_id]):
                prev = self._conversations[conversation_id][turn_index].is_positive
                self._conversations[conversation_id][turn_index].is_positive = is_positive
                
                # Undo previous feedback
                if prev is True: self._thumbs_up -= 1
                elif prev is False: self._thumbs_down -= 1
                
                # Apply new feedback
                if is_positive is True: self._thumbs_up += 1
                elif is_positive is False: self._thumbs_down += 1

    def log_query_metrics(self, confidence: float) -> None:
        self._total_queries += 1
        self._confidence_sum += confidence

    def get_global_metrics(self) -> dict:
        avg = (self._confidence_sum / self._total_queries) if self._total_queries > 0 else 0.0
        return {
            "total_queries": self._total_queries,
            "average_confidence": round(avg, 2),
            "thumbs_up": self._thumbs_up,
            "thumbs_down": self._thumbs_down
        }"""

text = text.replace(target_log, replacement_log)

with open("apps/api/src/rag_api/services/conversation.py", "w") as f:
    f.write(text)

