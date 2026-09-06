import json, uuid
from dataclasses import asdict
import redis
from rag_api.services.conversation import Turn, ConversationStore

class RedisConversationStore:
    """Same interface as ConversationStore -- get_history/append_turn/
    create_conversation -- so deps.py swaps the implementation with no
    call-site changes anywhere else."""

    def __init__(self, redis_url: str, ttl_seconds: int = 86400):
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds

    def get_history(self, conversation_id: str) -> list[Turn]:
        raw = self._client.get(f"conv:{conversation_id}")
        return [Turn(**t) for t in json.loads(raw)] if raw else []

    def append_turn(self, conversation_id: str, turn: Turn) -> None:
        history = self.get_history(conversation_id)
        history.append(turn)
        self._client.setex(f"conv:{conversation_id}", self._ttl, json.dumps([asdict(t) for t in history]))

    def create_conversation(self) -> str:
        cid = str(uuid.uuid4())
        self._client.setex(f"conv:{cid}", self._ttl, json.dumps([]))
        return cid
