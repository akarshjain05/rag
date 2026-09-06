from fastapi import Header, HTTPException, Depends
from rag_api.core.settings import Settings, get_settings

async def verify_api_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.api_keys:
        return  # empty list = auth disabled -- local dev only, never in a deployed env
    if x_api_key not in settings.api_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
