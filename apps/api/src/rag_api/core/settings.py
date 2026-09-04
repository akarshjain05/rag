"""Central configuration for the RAG pipeline.

All values are overridable via environment variables or a `.env` file.
See `.env.example` for the full list with comments.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Embeddings -----------------------------------------------------
    # "openai"  -> text-embedding-3-small (paid, needs OPENAI_API_KEY)
    # "local"   -> sentence-transformers, free, runs on CPU, no API key
    embedding_provider: str = "openai"
    openai_embedding_model: str = "text-embedding-3-small"
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    # --- Generation -------------------------------------------------------
    # "anthropic" -> Claude (needs ANTHROPIC_API_KEY)
    # "openai"    -> GPT-4o (needs OPENAI_API_KEY)
    # "none"      -> no LLM call at all; extractive fallback (zero API keys needed)
    llm_provider: str = "anthropic"
    anthropic_model: str = "claude-sonnet-4-5"
    openai_llm_model: str = "gpt-4o"
    anthropic_api_key: str | None = None

    # --- Storage ----------------------------------------------------------
    data_dir: Path = Path("./data")
    chroma_mode: str = "embedded"  # "embedded" (PersistentClient, local dir) | "http" (separate Chroma server)
    chroma_persist_dir: Path = Path("./data/chroma")  # used when chroma_mode == "embedded"
    chroma_host: str = "chromadb"  # used when chroma_mode == "http"; default matches the docker-compose service name
    chroma_port: int = 8000
    collection_name: str = "internal_docs"

    # --- Chunking -----------------------------------------------------------
    default_chunking_strategy: str = "structure_aware"  # fixed_size | structure_aware | semantic
    fixed_chunk_size: int = 1000
    fixed_chunk_overlap: int = 150
    structure_max_section_size: int = 1200  # sub-split sections larger than this
    semantic_similarity_threshold: float = 0.55  # lower => new chunk boundary
    semantic_max_chunk_chars: int = 1500  # safety cap regardless of similarity
    semantic_min_chunk_chars: int = 200  # avoid one-sentence micro-chunks

    # --- PDF Extraction -----------------------------------------------------
    pdf_extraction_backend: str = "pdfplumber"  # pdfplumber | pymupdf
    pdf_heading_font_ratio: float = 1.15
    pdf_max_heading_levels: int = 3
    pdf_table_extraction_enabled: bool = True
    pdf_image_captioning_enabled: bool = False

    # --- Deduplication ------------------------------------------------------
    dedup_similarity_threshold: float = 0.95

    # --- Retrieval ------------------------------------------------------------
    dense_top_k: int = 10
    sparse_top_k: int = 10
    hybrid_top_k: int = 5
    rrf_k: int = 60  # Reciprocal Rank Fusion constant
    rrf_dense_weight: float = 1.0
    rrf_sparse_weight: float = 1.0

    # --- Reranking (optional second pass over the fused pool) -----------------
    reranker_provider: str = "none"  # none | cross_encoder | llm_judge
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_candidate_pool: int = 20

    # --- Generation quality: citation verification, confidence, graceful "I don't know" ---
    citation_verification_enabled: bool = True  # LLM-as-judge; no-ops automatically without an LLM client
    citation_verification_strictness: str = "lenient"  # "lenient" | "strict"
    citation_verifier_model: str | None = None
    llm_request_timeout_seconds: float = 30.0
    low_confidence_threshold: float = 0.3  # retrieval confidence below this skips generation entirely
    image_indexing_enabled: bool = False
    ocr_engine: str = "tesseract"
    scanned_page_text_threshold: int = 20
    image_captioning_enabled: bool = False
    image_store_backend: str = "local"
    image_store_path: str = "/app/data/images"
    sparse_index_provider: str = "in_memory"
    sparse_index_persist_dir: str = "/app/data/sparse_index"
    structure_aware_semantic_fallback_enabled: bool = True
    text_heading_detection_enabled: bool = False

    # --- API -----------------------------------------------------------------
    api_port: int = 8000
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
