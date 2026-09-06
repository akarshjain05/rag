from fastapi import APIRouter, Depends
from rag_api.api.auth import verify_api_key
from rag_api.api.deps import get_conversation_store
import secrets
from pydantic import BaseModel
import time

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("", summary="Verify API Key")
def verify_auth(
    _=Depends(verify_api_key)
):
    return {"status": "ok"}

class GenerateKeyResponse(BaseModel):
    api_key: str
    created_at: float

@router.post("/keys", summary="Generate a new API key")
def generate_api_key(store=Depends(get_conversation_store), _=Depends(verify_api_key)):
    if not hasattr(store, "_client"):
        return {"error": "Redis not configured"}
    
    new_key = "sk-nx-" + secrets.token_hex(16)
    timestamp = time.time()
    
    store._client.sadd("api_keys:active", new_key)
    store._client.hset(f"api_key_meta:{new_key}", "created_at", str(timestamp))
    
    return GenerateKeyResponse(api_key=new_key, created_at=timestamp)

@router.get("/keys", summary="List generated API keys")
def list_api_keys(store=Depends(get_conversation_store), _=Depends(verify_api_key)):
    if not hasattr(store, "_client"):
        return []
        
    keys = store._client.smembers("api_keys:active")
    result = []
    for k in keys:
        meta = store._client.hgetall(f"api_key_meta:{k}")
        result.append({
            "api_key": k,
            "created_at": float(meta.get("created_at", 0))
        })
    return sorted(result, key=lambda x: x["created_at"], reverse=True)

@router.delete("/keys/{key}", summary="Revoke an API key")
def revoke_api_key(key: str, store=Depends(get_conversation_store), _=Depends(verify_api_key)):
    if not hasattr(store, "_client"):
        return {"status": "error"}
    
    store._client.srem("api_keys:active", key)
    store._client.delete(f"api_key_meta:{key}")
    return {"status": "ok"}
