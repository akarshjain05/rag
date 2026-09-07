from fastapi import APIRouter, Depends
from pydantic import BaseModel

class FeedbackRequest(BaseModel):
    turn_index: int
    is_positive: bool | None = None

from rag_api.api.deps import get_conversation_store
from rag_api.api.auth import verify_api_key

router = APIRouter(prefix="/conversations", tags=["conversations"], dependencies=[Depends(verify_api_key)])

@router.get("", summary="List conversations")
def list_conversations(store=Depends(get_conversation_store)):
    return {"conversations": store.list_conversations()}

@router.get("/{conversation_id}", summary="Get conversation history")
def get_conversation(conversation_id: str, store=Depends(get_conversation_store)):
    return {"history": store.get_history(conversation_id)}

@router.post("/{conversation_id}/feedback", summary="Submit feedback for a turn")
def submit_feedback(conversation_id: str, payload: FeedbackRequest, store=Depends(get_conversation_store)):
    store.update_turn_feedback(conversation_id, payload.turn_index, payload.is_positive)
    return {"status": "ok"}

@router.delete("/{conversation_id}", summary="Delete conversation")
def delete_conversation(conversation_id: str, store=Depends(get_conversation_store)):
    store.delete_conversation(conversation_id)
    return {"status": "deleted"}
