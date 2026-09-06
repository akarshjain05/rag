from fastapi import Request
from rag_api.core.settings import Settings

def get_settings(request: Request) -> Settings:
    return request.app.state.settings

def get_pipeline(request: Request):
    return request.app.state.pipeline

def get_retriever(request: Request):
    return request.app.state.retriever

def get_generator(request: Request):
    return request.app.state.generator

def get_vector_store(request: Request):
    return request.app.state.vector_store


def run_or_502(fn, *args, **kwargs):
    from fastapi import HTTPException
    from openai import OpenAIError
    from anthropic import AnthropicError
    try:
        return fn(*args, **kwargs)
    except (OpenAIError, AnthropicError) as exc:
        raise HTTPException(status_code=502, detail=f"Upstream AI provider error: {exc}") from exc

def get_conversation_store(request: Request):
    return request.app.state.conversation_store

def get_llm_client(request: Request):
    return request.app.state.llm_client

async def run_or_502_async(coro):
    from fastapi import HTTPException
    from openai import OpenAIError
    from anthropic import AnthropicError
    try:
        return await coro
    except (OpenAIError, AnthropicError) as exc:
        raise HTTPException(status_code=502, detail=f"Upstream AI provider error: {exc}") from exc

def get_object_store(request: Request):
    settings = request.app.state.settings
    from rag_api.adapters.storage.object_store import ObjectStore
    return ObjectStore(
        settings.object_store_endpoint or "http://minio:9000",
        settings.object_store_access_key or "minioadmin",
        settings.object_store_secret_key or "minioadminpassword",
        settings.object_store_bucket
    )
