import shutil
import tempfile
import asyncio
import json
import concurrent.futures
from pathlib import Path
from fastapi import APIRouter, Depends, File, Query, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from rag_api.schemas.schemas import IngestResponse, IngestReportSchema, DocumentsResponse, DeleteResponse
from rag_api.domain.models import ChunkingStrategy
from rag_api.api.deps import get_pipeline, get_vector_store, run_or_502

router = APIRouter(prefix="", tags=["documents"])

@router.post(
    "/ingest",
    summary="Ingest one or more documents (SSE Stream)",
    description="Accepts markdown, plaintext, HTML or PDF files (repeatable `files` field). Each file is loaded, chunked, embedded, deduplicated against the existing index, and added to both the dense and sparse indexes. One broken file doesn't fail the whole batch -- check each report's `error` field.",
)
async def ingest_documents(
    files: list[UploadFile] = File(...),
    chunking_strategy: ChunkingStrategy | None = Query(default=None),
    pipeline = Depends(get_pipeline)
):
    tmp_dir = Path(tempfile.mkdtemp(prefix="rag_ingest_"))
    saved_paths = []
    for f in files:
        if not f.filename: continue
        dest = tmp_dir / Path(f.filename).name
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        saved_paths.append(dest)

    if not saved_paths:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="No valid files provided")

    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def progress_callback(progress, message):
        asyncio.run_coroutine_threadsafe(
            queue.put({"progress": progress, "message": message}), loop
        )

    def worker():
        try:
            reports = pipeline.ingest_files(saved_paths, strategy=chunking_strategy, progress_callback=progress_callback)
            asyncio.run_coroutine_threadsafe(
                queue.put({"reports": [vars(r) for r in reports]}), loop
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                queue.put({"error": str(e)}), loop
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    executor.submit(worker)

    async def sse_generator():
        yield f"data: {json.dumps({'progress': 0, 'message': 'Processing started...'})}\n\n"
        while True:
            item = await queue.get()
            yield f"data: {json.dumps(item)}\n\n"
            if "reports" in item or "error" in item:
                break

    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@router.get("/documents", response_model=DocumentsResponse, summary="List indexed documents")
def list_documents(vector_store = Depends(get_vector_store)) -> DocumentsResponse:
    return DocumentsResponse(
        source_documents=vector_store.list_source_documents(),
        total_chunks=vector_store.count(),
    )

@router.delete("/documents/{source_document}", response_model=DeleteResponse, summary="Remove a document from the index", description="Deletes every chunk (across all chunking strategies) belonging to `source_document` from both the vector store and the sparse index.")
def delete_document(
    source_document: str,
    vector_store = Depends(get_vector_store),
) -> DeleteResponse:
    deleted = vector_store.delete_source_document(source_document)
    return DeleteResponse(source_document=source_document, chunks_deleted=deleted)
