import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, Query, UploadFile, HTTPException
from rag_api.schemas.schemas import IngestResponse, IngestReportSchema, DocumentsResponse, DeleteResponse
from rag_api.domain.models import ChunkingStrategy
from rag_api.api.deps import get_pipeline, get_vector_store, get_sparse_index, run_or_502

router = APIRouter(prefix="", tags=["documents"])

@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest one or more documents",
    description="Accepts markdown, plaintext, HTML or PDF files (repeatable `files` field). Each file is loaded, chunked, embedded, deduplicated against the existing index, and added to both the dense and sparse indexes. One broken file doesn't fail the whole batch -- check each report's `error` field.",
)
async def ingest_documents(
    files: list[UploadFile] = File(...),
    chunking_strategy: ChunkingStrategy | None = Query(default=None),
    pipeline = Depends(get_pipeline)
) -> IngestResponse:
    tmp_dir = Path(tempfile.mkdtemp(prefix="rag_ingest_"))
    try:
        saved_paths = []
        for f in files:
            if not f.filename: continue
            dest = tmp_dir / Path(f.filename).name
            with dest.open("wb") as out:
                shutil.copyfileobj(f.file, out)
            saved_paths.append(dest)

        if not saved_paths:
            raise HTTPException(status_code=400, detail="No valid files provided")

        reports = run_or_502(pipeline.ingest_files, saved_paths, strategy=chunking_strategy)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return IngestResponse(reports=[IngestReportSchema(**vars(r)) for r in reports])

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
    sparse_index = Depends(get_sparse_index)
) -> DeleteResponse:
    deleted = vector_store.delete_source_document(source_document)
    sparse_index.delete_source_document(source_document)
    return DeleteResponse(source_document=source_document, chunks_deleted=deleted)
