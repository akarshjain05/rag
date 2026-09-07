from fastapi import Header, HTTPException, Request

async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> None:
    settings = request.app.state.settings
    if not settings.api_keys:
        return
        
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    
    if x_api_key in settings.api_keys:
        return

    raise HTTPException(status_code=401, detail="Invalid or missing API key")
