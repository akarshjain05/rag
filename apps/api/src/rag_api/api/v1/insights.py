from fastapi import APIRouter, Depends
from rag_api.api.auth import verify_api_key
from rag_api.api.deps import get_conversation_store
from rag_api.services.redis_conversation import RedisConversationStore

router = APIRouter(prefix="/insights", tags=["insights"], dependencies=[Depends(verify_api_key)])

@router.get("", summary="Get global insights and metrics")
def get_insights(store=Depends(get_conversation_store)):
    return store.get_global_metrics()
