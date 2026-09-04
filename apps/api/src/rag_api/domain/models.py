"""Internal dataclasses shared across loaders, chunking, indexing and retrieval.

Kept separate from `app/schemas.py` (the API's pydantic request/response models)
so the core pipeline has no FastAPI/pydantic coupling and can be unit tested,
scripted, or reused outside the web layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ChunkingStrategy(str, Enum):
    FIXED_SIZE = "fixed_size"
    STRUCTURE_AWARE = "structure_aware"
    SEMANTIC = "semantic"


@dataclass
class PageText:
    """One page of extracted text (PDF only). page_number is 1-indexed."""

    page_number: int
    text: str
    extraction_method: str = "native"


@dataclass
class LoadedDocument:
    """Normalized output of a document loader, regardless of source format.

    `text` is the full plaintext with markdown-style '#'..'######' heading
    markers so downstream chunkers can treat every source format uniformly.
    `pages` is populated only for PDFs (page-accurate text, no heading
    normalization within a page); it is None for md/txt/html.
    """

    source_file: str
    format: str  # "md" | "txt" | "html" | "pdf"
    text: str
    pages: list[PageText] | None = None


@dataclass
class Chunk:
    """A single chunk ready for embedding + indexing."""

    text: str
    source_document: str
    chunking_strategy: str
    chunk_index: int
    section_heading: str | None = None
    page_number: int | None = None
    image_ref: str | None = None
    content_type: str | None = None
    extraction_method: str | None = None
    char_count: int = field(init=False)
    chunk_id: str = field(init=False)

    def __post_init__(self) -> None:
        self.char_count = len(self.text)
        safe_source = self.source_document.replace("/", "_").replace(" ", "_")
        self.chunk_id = f"{safe_source}::{self.chunking_strategy}::{self.chunk_index}"

    def metadata(self) -> dict:
        """Chroma/BM25 metadata dict. No `None`s — Chroma metadata values
        must be str/int/float/bool, so absent fields get sentinel defaults."""
        return {
            "source_document": self.source_document,
            "chunk_index": self.chunk_index,
            "section_heading": self.section_heading or "",
            "chunking_strategy": self.chunking_strategy,
            "char_count": self.char_count,
            "page_number": self.page_number if self.page_number is not None else -1,
            "image_ref": self.image_ref or "",
            "content_type": self.content_type or "",
            "extraction_method": self.extraction_method or "",
        }


@dataclass
class RetrievedChunk:
    """A chunk returned from retrieval, with scoring provenance."""

    chunk_id: str
    text: str
    metadata: dict
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fused_score: float = 0.0
    rerank_score: float | None = None
    dense_similarity: float | None = None  # raw cosine similarity, when the chunk came from dense search


@dataclass
class ClaimVerification:
    """One sentence-level claim from a generated answer, the citation
    marker(s) it carried, and whether an LLM-judge confirmed the cited
    excerpt(s) actually support it. `supported` is None when verification
    didn't run (disabled, or no LLM available) -- distinct from False."""

    claim_text: str
    citation_markers: list[int]
    supported: bool | None = None


@dataclass
class IngestReport:
    source_file: str
    chunking_strategy: str
    chunks_created: int = 0
    chunks_inserted: int = 0
    duplicates_skipped: int = 0
    duplicate_of: list[str] = field(default_factory=list)
    error: str | None = None
