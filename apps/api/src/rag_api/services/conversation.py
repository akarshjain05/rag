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
        self.max_size = max_size
        
    def _evict_if_needed(self):
        while len(self._metadata) > self.max_size:
            cid, _ = self._metadata.popitem(last=False)
            if cid in self._conversations:
                del self._conversations[cid]

    def get_history(self, conversation_id: str) -> List[Turn]:
        return self._conversations.get(conversation_id, [])

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
                self._conversations[conversation_id][turn_index].is_positive = is_positive

    def log_query_metrics(self, confidence: float) -> None:
        pass
