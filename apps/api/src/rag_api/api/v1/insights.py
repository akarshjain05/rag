from fastapi import APIRouter, Depends
from rag_api.api.deps import get_conversation_store
from rag_api.services.redis_conversation import RedisConversationStore

router = APIRouter(prefix="/insights", tags=["insights"])

@router.get("", summary="Get global insights and metrics")
def get_insights(store=Depends(get_conversation_store)):
    # Fallback for in-memory store
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
    }
