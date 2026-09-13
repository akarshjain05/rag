import uuid
import time
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class Turn:
    user: str
    assistant: str
    is_positive: bool | None = None
    sources: List[dict] | None = None
    confidence_info: dict | None = None

from collections import OrderedDict

class ConversationStore:
    def __init__(self, max_size: int = 1000):
        self._conversations: Dict[str, List[Turn]] = {}
        self._metadata: OrderedDict[str, dict] = OrderedDict()
        self._interrupted: Dict[str, str] = {}
        self.max_size = max_size
        self._total_queries = 0
        self._confidence_sum = 0.0
        self._thumbs_up = 0
        self._thumbs_down = 0
        
    def _evict_if_needed(self):
        while len(self._metadata) > self.max_size:
            cid, _ = self._metadata.popitem(last=False)
            if cid in self._conversations:
                del self._conversations[cid]

    def get_history(self, conversation_id: str) -> List[Turn]:
        return self._conversations.get(conversation_id, [])

    def mark_interrupted(self, conversation_id: str, question: str) -> None:
        """Records the question in flight when the client disconnected (Stop),
        so an immediate 'continue' can resume it. Overwrites any prior pending
        question -- only the most recent stop is resumable."""
        self._interrupted[conversation_id] = question

    def pop_interrupted(self, conversation_id: str) -> str | None:
        """One-shot: consumed whether or not the caller ends up using it, so it
        can't resurface for some unrelated later message."""
        return self._interrupted.pop(conversation_id, None)

    def append_turn(self, conversation_id: str, turn: Turn) -> None:
        self._evict_if_needed()
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
        if not self._conversations[conversation_id]:
            self._metadata[conversation_id] = {
                "title": turn.user[:50] + ("..." if len(turn.user) > 50 else ""),
                "updated_at": time.time()
            }
        else:
            if conversation_id in self._metadata:
                self._metadata[conversation_id]["updated_at"] = time.time()
                self._metadata.move_to_end(conversation_id)
                
        self._conversations[conversation_id].append(turn)
        
    def create_conversation(self) -> str:
        cid = str(uuid.uuid4())
        self._conversations[cid] = []
        self._metadata[cid] = {"title": "New Conversation", "updated_at": time.time()}
        self._evict_if_needed()
        return cid

    def list_conversations(self) -> list[dict]:
        result = []
        for cid, meta in self._metadata.items():
            result.append({"id": cid, "title": meta.get("title", "New Conversation"), "updated_at": meta.get("updated_at", 0)})
        return sorted(result, key=lambda x: x["updated_at"], reverse=True)

    def delete_conversation(self, conversation_id: str) -> None:
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
        if conversation_id in self._metadata:
            del self._metadata[conversation_id]

    def update_turn_feedback(self, conversation_id: str, turn_index: int, is_positive: bool | None) -> None:
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
        }
