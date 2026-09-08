import logging
from fastapi import APIRouter, Request, Depends, BackgroundTasks

from rag_api.schemas.schemas import QueryRequest, QueryResponse
from rag_api.api.deps import get_orchestrator
from rag_api.api.auth import verify_api_key

log = logging.getLogger("rag_api")

router = APIRouter(prefix="", tags=["ask"], dependencies=[Depends(verify_api_key)])

@router.post("/ask", response_model=QueryResponse)
async def ask(
    payload: QueryRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    orchestrator = Depends(get_orchestrator),
) -> QueryResponse:
    # Set the background tasks on the orchestrator directly for this request lifecycle
    orchestrator.background_tasks = background_tasks
    return await orchestrator.answer_query(payload, request)
