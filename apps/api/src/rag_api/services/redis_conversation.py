import json, uuid, time
from dataclasses import asdict
import redis
from rag_api.services.conversation import Turn, ConversationStore

class RedisConversationStore:
    def __init__(self, redis_url: str, ttl_seconds: int = 86400 * 7):
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds

    def get_history(self, conversation_id: str) -> list[Turn]:
        raw = self._client.get(f"conv:{conversation_id}")
        return [Turn(**t) for t in json.loads(raw)] if raw else []

    def append_turn(self, conversation_id: str, turn: Turn) -> None:
        history = self.get_history(conversation_id)
        if not history:
            title = turn.user[:50] + ("..." if len(turn.user) > 50 else "")
            self._client.hset(f"conv_meta:{conversation_id}", mapping={"title": title, "updated_at": str(time.time())})
        else:
            self._client.hset(f"conv_meta:{conversation_id}", "updated_at", str(time.time()))
        history.append(turn)
        self._client.setex(f"conv:{conversation_id}", self._ttl, json.dumps([asdict(t) for t in history]))
        self._client.sadd("conversations:all", conversation_id)

    def create_conversation(self) -> str:
        cid = str(uuid.uuid4())
        self._client.setex(f"conv:{cid}", self._ttl, json.dumps([]))
        self._client.hset(f"conv_meta:{cid}", mapping={"title": "New Conversation", "updated_at": str(time.time())})
        self._client.sadd("conversations:all", cid)
        return cid

    def list_conversations(self) -> list[dict]:
        cids = self._client.smembers("conversations:all")
        result = []
        for cid in cids:
            meta = self._client.hgetall(f"conv_meta:{cid}")
            if meta:
                result.append({
                    "id": cid,
                    "title": meta.get("title", "New Conversation"),
                    "updated_at": float(meta.get("updated_at", 0))
                })
        return sorted(result, key=lambda x: x["updated_at"], reverse=True)
