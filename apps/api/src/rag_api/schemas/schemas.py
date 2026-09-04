"""Pydantic schemas for the HTTP API. Kept separate from `app/models.py`
(plain dataclasses used by the core pipeline) so the pipeline has zero
FastAPI/pydantic coupling and stays usable as a plain library or script."""
from __future__ import annotations

from pydantic import BaseModel, Field

from rag_api.domain.models import ChunkingStrategy


class IngestReportSchema(BaseModel):
    source_file: str
    chunking_strategy: str
    chunks_created: int = 0
    chunks_inserted: int = 0
    duplicates_skipped: int = 0
    duplicate_of: list[str] = Field(default_factory=list)
    error: str | None = None


class IngestResponse(BaseModel):
    reports: list[IngestReportSchema]


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    conversation_id: str | None = None
    verify_citations: bool | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    chunking_strategy: ChunkingStrategy | None = None
    compare_dense_only: bool = Field(
        default=False, description="Also return dense-only retrieval results alongside the normal hybrid answer, for side-by-side comparison."
    )
    image_url: str | None = Field(default=None, description="Optional image URL to analyze alongside the text context")


class SourceSchema(BaseModel):
    marker: int
    chunk_id: str
    source_document: str | None = None
    section_heading: str | None = None
    page_number: int | None = None
    dense_rank: int | None = None
    sparse_rank: int | None = None
    rerank_score: float | None = None


class QueryResponse(BaseModel):
    conversation_id: str | None = None
    answer: str
    mode: str
    sources: list[SourceSchema]
    used_citation_markers: list[int]
    invalid_citation_markers: list[int]
    unsupported_citation_markers: list[int] = Field(default_factory=list)
    retrieval_confidence: float | None = None
    citation_coverage: float | None = None
    citation_coverage_basis: str | None = None
    completeness: float | None = None
    composite_confidence: float | None = None
    dense_only_sources: list[SourceSchema] | None = Field(
        default=None, description="Populated only when the request set compare_dense_only=true."
    )


class DocumentsResponse(BaseModel):
    source_documents: list[str]
    total_chunks: int


class DeleteResponse(BaseModel):
    source_document: str
    chunks_deleted: int


class HealthResponse(BaseModel):
    status: str
    indexed_chunks: int
    embedding_provider: str
    llm_provider: str
    llm_mode: str
    reranker_provider: str
    citation_verification_enabled: bool
    low_confidence_threshold: float
