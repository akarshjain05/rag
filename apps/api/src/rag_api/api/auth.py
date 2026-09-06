from fastapi import Header, HTTPException, Depends, Request
from rag_api.core.settings import Settings

async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> None:
    settings = request.app.state.settings
    if not settings.api_keys:
        return
    
    if x_api_key in settings.api_keys:
        return

    store = request.app.state.conversation_store
    if hasattr(store, "_client"):
        is_member = store._client.sismember("api_keys:active", x_api_key)
        if is_member:
            return

    raise HTTPException(status_code=401, detail="Invalid or missing API key")
