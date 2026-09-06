from fastapi import APIRouter, Depends
from rag_api.api.deps import get_conversation_store

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.get("", summary="List conversations")
def list_conversations(store=Depends(get_conversation_store)):
    return {"conversations": store.list_conversations()}

@router.get("/{conversation_id}", summary="Get conversation history")
def get_conversation(conversation_id: str, store=Depends(get_conversation_store)):
    return {"history": store.get_history(conversation_id)}
