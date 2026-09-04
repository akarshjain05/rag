import pytest
from rag_api.domain.chunking.chunking import chunk_document
from rag_api.domain.models import LoadedDocument, ChunkingStrategy
from rag_api.core.settings import get_settings
from rag_api.adapters.vectorstore.embeddings import EmbeddingClient

class DummyEmbeddingClient(EmbeddingClient):
    @property
    def dimension(self):
        return 384

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Dummy vectors
        return [[0.1] * 384 for _ in texts]

def test_structure_aware_semantic_fallback():
    settings = get_settings()
    # Unstructured text without headings
    doc = LoadedDocument(source_file="test.txt", format="txt", text="Sentence one. Sentence two. Sentence three. Sentence four.")
    
    # Enable fallback
    settings.structure_aware_semantic_fallback_enabled = True
    
    client = DummyEmbeddingClient()
    
    # Even with STRUCTURE_AWARE, because there are no headings and the fallback is enabled,
    # it should route to the semantic logic (or recursive if no embedding client).
    # Since we pass an embedding client, it should do semantic logic.
    chunks, _ = chunk_document(doc, ChunkingStrategy.STRUCTURE_AWARE, embedding_client=client, semantic_min_chunk_chars=10, semantic_max_chunk_chars=50)
    
    assert len(chunks) > 0
    assert "Document: test.txt" in chunks[0].text

from rag_api.domain.chunking.chunking import _structure_aware_split, _is_low_quality_chunk
from rag_api.domain.models import IngestReport

def test_structure_aware_merges_tiny_sections():
    # A synthetic doc with a bolded lone number between real sections
    # simulated here as markdown headings (since _structure_aware_split consumes markdown text).
    text = "# Section 1\n\nThis is real content for section 1.\n\n# 325\n\n# Section 2\n\nThis is real content for section 2."
    
    # We set min_section_chars=40. "325" is smaller than 40.
    # It should merge "325" into "Section 1", and then "Section 2" is normal.
    out = _structure_aware_split(text, max_section_size=1000, min_section_chars=40)
    
    # We expect 2 chunks, not 3.
    assert len(out) == 2
    # Chunk 1 should contain the merged tiny section
    assert "325" in out[0][0]
    # No chunk should be less than 40 chars
    for chunk_text, _ in out:
        assert len(chunk_text) >= 40

def test_low_quality_chunk_filter():
    assert _is_low_quality_chunk("325", min_chars=20, min_alpha_ratio=0.2) is True
    assert _is_low_quality_chunk("...", min_chars=20, min_alpha_ratio=0.2) is True
    assert _is_low_quality_chunk("This is a legitimate short sentence.", min_chars=20, min_alpha_ratio=0.2) is False

def test_ingest_reports_skipped_low_quality_chunks():
    # A document with *only* a low quality chunk. If we use fixed size with a large limit,
    # it groups them. So we just pass the garbage directly to ensure it gets skipped.
    doc = LoadedDocument(source_file="test.txt", format="txt", text="325")
    chunks, skipped = chunk_document(doc, ChunkingStrategy.FIXED_SIZE, fixed_chunk_size=1000)
    
    assert len(chunks) == 0
    assert skipped == 1
