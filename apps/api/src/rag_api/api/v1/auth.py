from fastapi import APIRouter, Depends
from rag_api.api.deps import verify_api_key

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("", summary="Verify API Key")
def verify_auth(
    _=Depends(verify_api_key)
):
    return {"status": "ok"}
