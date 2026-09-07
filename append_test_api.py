with open("apps/api/tests/unit/test_api.py", "a") as f:
    f.write("""

def test_typo_query_recovers_via_normalization(tmp_path):
    from unittest.mock import MagicMock
    from rag_api.core.settings import Settings
    from rag_api.main import create_app
    from fastapi.testclient import TestClient
    from rag_api.adapters.vectorstore.vector_store import VectorStore
    from rag_api.adapters.sparse.sparse_index import SparseIndex
    
    class DeterministicFakeEmbeddingClient:
        def embed(self, texts):
            return [[0.1] * 768 for _ in texts]
        def embed_query(self, text):
            return [0.1] * 768
            
    fake_llm = MagicMock()
    fake_llm.provider_name = "fake"
    def fake_generate(system, user, history=None):
        if "clean up a user's search query" in system.lower():
            return "watermarking"
        return "Watermarking embeds a hidden identifier [1]."
    fake_llm.generate.side_effect = fake_generate

    class ScoreByQueryReranker:
        def rerank(self, query, candidates, top_k):
            score = 0.85 if query == "watermarking" else 0.0
            for c in candidates:
                c.rerank_score = score
            return candidates[:top_k]

    settings = Settings(chroma_persist_dir=tmp_path / "chroma")
    app = create_app(
        settings, embedding_client=DeterministicFakeEmbeddingClient(), llm_client=fake_llm,
        vector_store=VectorStore(tmp_path / "chroma", settings.collection_name),
        sparse_index=SparseIndex(), reranker=ScoreByQueryReranker(),
    )
    client = TestClient(app)
    client.post("/v1/ingest", files=[("files", ("wm.md", b"# Watermarking\\n\\nWatermarking embeds a hidden identifier in digital content.", "text/markdown"))])

    resp = client.post("/v1/ask", json={"question": "what is wtaermakring?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] != "low_confidence"
    assert body["retrieval_confidence"] > 0.3
""")
