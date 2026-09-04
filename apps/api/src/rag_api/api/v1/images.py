from fastapi import APIRouter, Depends, HTTPException, Request, Response
from rag_api.adapters.storage.image_store import ImageStore

router = APIRouter(prefix="/images", tags=["images"])

def get_image_store(request: Request) -> ImageStore:
    return request.app.state.image_store

@router.get("/{image_hash}")
def get_image(image_hash: str, image_store: ImageStore = Depends(get_image_store)):
    result = image_store.get(image_hash)
    if not result:
        raise HTTPException(status_code=404, detail="Image not found")
    
    img_bytes, content_type = result
    return Response(content=img_bytes, media_type=content_type)
