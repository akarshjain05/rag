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
    chunks = chunk_document(doc, ChunkingStrategy.STRUCTURE_AWARE, embedding_client=client, semantic_min_chunk_chars=10, semantic_max_chunk_chars=50)
    
    assert len(chunks) > 0
    assert "Document: test.txt" in chunks[0].text
