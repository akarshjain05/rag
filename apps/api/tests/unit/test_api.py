from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from rag_api.main import create_app
from rag_api.core.settings import Settings
from rag_api.adapters.vectorstore.embeddings import DeterministicFakeEmbeddingClient
from rag_api.domain.retrieval.reranker import LLMJudgeReranker
from rag_api.adapters.vectorstore.sparse_index import SparseIndex
from rag_api.adapters.vectorstore.vector_store import VectorStore


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        chroma_persist_dir=tmp_path / "chroma",
        default_chunking_strategy="structure_aware",
        structure_max_section_size=500,
    )
    app = create_app(
        settings,
        embedding_client=DeterministicFakeEmbeddingClient(dimension=128),
        llm_mode="extractive",  # exercises the full pipeline with zero API keys
        vector_store=VectorStore(tmp_path / "chroma", settings.collection_name),
        sparse_index=SparseIndex(),
    )
    return TestClient(app)


MD_CONTENT = b"""# Handbook

## Vacation Policy

Employees accrue vacation days at a rate of 1.5 days per month.

## Remote Work Policy

Employees may work remotely up to three days per week with manager approval.
"""


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["indexed_chunks"] == 0
    assert body["llm_mode"] == "extractive"


def test_ingest_then_documents_endpoint(client):
    resp = client.post("/v1/ingest", files=[("files", ("handbook.md", MD_CONTENT, "text/markdown"))])
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["reports"]) == 1
    report = body["reports"][0]
    assert report["source_file"] == "handbook.md"
    assert report["error"] is None
    assert report["chunks_inserted"] > 0

    docs_resp = client.get("/v1/documents")
    assert docs_resp.status_code == 200
    docs = docs_resp.json()
    assert docs["source_documents"] == ["handbook.md"]
    assert docs["total_chunks"] == report["chunks_inserted"]


def test_ingest_missing_files_field_is_rejected(client):
    # no `files` part in the multipart body at all -> FastAPI's own required-
    # field validation (422) fires before our handler's empty-list check does
    resp = client.post("/v1/ingest", files=[])
    assert resp.status_code == 422


def test_query_after_ingest_returns_grounded_answer_with_sources(client):
    client.post("/v1/ingest", files=[("files", ("handbook.md", MD_CONTENT, "text/markdown"))])

    resp = client.post("/v1/ask", json={"question": "How many vacation days do employees accrue per month?", "top_k": 3})

    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "extractive"
    assert "[1]" in body["answer"]
    assert body["used_citation_markers"] == [1]
    assert body["invalid_citation_markers"] == []
    assert body["sources"][0]["source_document"] == "handbook.md"


def test_query_on_empty_index_returns_no_context(client):
    resp = client.post("/v1/ask", json={"question": "anything at all"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "no_context"
    assert body["sources"] == []


def test_query_validates_top_k_bounds(client):
    resp = client.post("/v1/ask", json={"question": "hi", "top_k": 0})
    assert resp.status_code == 422
    resp = client.post("/v1/ask", json={"question": "hi", "top_k": 100})
    assert resp.status_code == 422


def test_ingest_respects_chunking_strategy_query_param(client):
    resp = client.post(
        "/v1/ingest?chunking_strategy=fixed_size",
        files=[("files", ("handbook.md", MD_CONTENT, "text/markdown"))],
    )
    assert resp.status_code == 200
    assert resp.json()["reports"][0]["chunking_strategy"] == "fixed_size"


def test_delete_document_removes_it_from_index(client):
    client.post("/v1/ingest", files=[("files", ("handbook.md", MD_CONTENT, "text/markdown"))])

    del_resp = client.delete("/v1/documents/handbook.md")
    assert del_resp.status_code == 200
    assert del_resp.json()["chunks_deleted"] > 0

    docs_resp = client.get("/v1/documents")
    assert docs_resp.json()["source_documents"] == []
    assert docs_resp.json()["total_chunks"] == 0


def test_query_translates_provider_failure_into_clean_502(tmp_path):
    from openai import OpenAIError

    class FailingEmbedder(DeterministicFakeEmbeddingClient):
        def embed(self, texts):
            raise OpenAIError("rate limit exceeded")

    settings = Settings(chroma_persist_dir=tmp_path / "chroma2")
    app = create_app(
        settings,
        embedding_client=FailingEmbedder(),
        llm_mode="extractive",
        vector_store=VectorStore(tmp_path / "chroma2", settings.collection_name),
        sparse_index=SparseIndex(),
    )
    failing_client = TestClient(app)

    resp = failing_client.post("/v1/ask", json={"question": "anything"})

    assert resp.status_code == 502
    assert "Upstream AI provider error" in resp.json()["detail"]


def test_ingest_bad_file_type_reports_error_without_500(client):
    resp = client.post("/v1/ingest", files=[("files", ("notes.docx", b"not really a docx", "application/octet-stream"))])
    assert resp.status_code == 200
    report = resp.json()["reports"][0]
    assert report["error"] is not None
    assert report["chunks_inserted"] == 0


def test_query_with_reranker_wired_returns_rerank_scores(tmp_path):
    class ReverseOrderReranker:
        """Deterministic test double: hands back the fused pool reversed,
        proving the query endpoint surfaces whatever the reranker decides
        rather than the raw fusion order."""

        def rerank(self, query, candidates, top_k):
            reordered = list(reversed(candidates))
            for i, c in enumerate(reordered):
                c.rerank_score = float(i)
            return reordered[:top_k]

    settings = Settings(chroma_persist_dir=tmp_path / "chroma3")
    store = VectorStore(tmp_path / "chroma3", settings.collection_name)
    app = create_app(
        settings,
        embedding_client=DeterministicFakeEmbeddingClient(),
        llm_mode="extractive",
        vector_store=store,
        sparse_index=SparseIndex(),
        reranker=ReverseOrderReranker(),
    )
    reranked_client = TestClient(app)
    reranked_client.post("/v1/ingest", files=[("files", ("handbook.md", MD_CONTENT, "text/markdown"))])

    resp = reranked_client.post("/v1/ask", json={"question": "vacation policy", "top_k": 2})

    assert resp.status_code == 200
    sources = resp.json()["sources"]
    assert all(s["rerank_score"] is not None for s in sources)

    health = reranked_client.get("/health").json()
    assert health["reranker_provider"] == "none"  # settings default -- override was via direct injection, not config


def test_reranker_auto_built_from_settings_when_not_overridden(tmp_path):
    """When `reranker` isn't passed to create_app at all (the _UNSET
    sentinel), it should be built from settings.reranker_provider -- as
    opposed to the test above, which bypasses that by injecting one
    directly."""
    fake_llm = MagicMock()
    fake_llm.generate.return_value = '{"1": 9}'

    settings = Settings(chroma_persist_dir=tmp_path / "chroma4", reranker_provider="llm_judge")
    app = create_app(
        settings,
        embedding_client=DeterministicFakeEmbeddingClient(),
        llm_client=fake_llm,
        vector_store=VectorStore(tmp_path / "chroma4", settings.collection_name),
        sparse_index=SparseIndex(),
    )

    assert isinstance(app.state.retriever.reranker, LLMJudgeReranker)
    assert TestClient(app).get("/health").json()["reranker_provider"] == "llm_judge"


def test_llm_client_auto_built_from_settings_when_nothing_overridden(tmp_path, monkeypatch):
    """The real default-wiring path: neither llm_client nor llm_mode passed
    to create_app at all, so it must build from settings.llm_provider --
    every other test in this file bypasses this branch via an override."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    settings = Settings(chroma_persist_dir=tmp_path / "chroma5", llm_provider="anthropic")

    app = create_app(
        settings,
        embedding_client=DeterministicFakeEmbeddingClient(),
        vector_store=VectorStore(tmp_path / "chroma5", settings.collection_name),
        sparse_index=SparseIndex(),
    )

    assert app.state.generator.mode == "llm"
    assert app.state.generator.llm_client is not None
    assert TestClient(app).get("/health").json()["llm_mode"] == "llm"


def test_ingest_empty_filename_rejected_by_upload_validation(client):
    # FastAPI's own UploadFile validation rejects an empty filename before
    # our handler's `if not f.filename` check would even run -- same class
    # of "framework validates first" as the missing-files-field case above.
    resp = client.post("/v1/ingest", files=[("files", ("", b"content", "text/plain"))])
    assert resp.status_code == 422


def test_citation_verifier_auto_built_when_llm_available_and_enabled(tmp_path):
    fake_llm = MagicMock()
    settings = Settings(chroma_persist_dir=tmp_path / "chroma6", citation_verification_enabled=True)

    app = create_app(
        settings,
        embedding_client=DeterministicFakeEmbeddingClient(),
        llm_client=fake_llm,
        vector_store=VectorStore(tmp_path / "chroma6", settings.collection_name),
        sparse_index=SparseIndex(),
    )

    assert app.state.generator.citation_verifier is not None
    assert TestClient(app).get("/health").json()["citation_verification_enabled"] is True


def test_citation_verifier_not_built_when_disabled_in_settings(tmp_path):
    fake_llm = MagicMock()
    settings = Settings(chroma_persist_dir=tmp_path / "chroma7", citation_verification_enabled=False)

    app = create_app(
        settings,
        embedding_client=DeterministicFakeEmbeddingClient(),
        llm_client=fake_llm,
        vector_store=VectorStore(tmp_path / "chroma7", settings.collection_name),
        sparse_index=SparseIndex(),
    )

    assert app.state.generator.citation_verifier is None
    assert TestClient(app).get("/health").json()["citation_verification_enabled"] is False


def test_citation_verifier_not_built_in_extractive_mode_even_if_enabled(tmp_path):
    """citation_verification_enabled=True is the default, but there's no
    LLM in extractive mode to judge with -- must no-op, not error."""
    settings = Settings(chroma_persist_dir=tmp_path / "chroma8", citation_verification_enabled=True)

    app = create_app(
        settings,
        embedding_client=DeterministicFakeEmbeddingClient(),
        llm_mode="extractive",
        vector_store=VectorStore(tmp_path / "chroma8", settings.collection_name),
        sparse_index=SparseIndex(),
    )

    assert app.state.generator.citation_verifier is None


def test_query_low_confidence_response_over_http(tmp_path):
    settings = Settings(chroma_persist_dir=tmp_path / "chroma9", low_confidence_threshold=0.99)  # near-impossible to clear
    store = VectorStore(tmp_path / "chroma9", settings.collection_name)
    app = create_app(
        settings,
        embedding_client=DeterministicFakeEmbeddingClient(),
        llm_mode="extractive",
        vector_store=store,
        sparse_index=SparseIndex(),
    )
    low_conf_client = TestClient(app)
    low_conf_client.post("/v1/ingest", files=[("files", ("handbook.md", MD_CONTENT, "text/markdown"))])

    resp = low_conf_client.post("/v1/ask", json={"question": "vacation policy", "top_k": 2})

    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "low_confidence"
    assert body["retrieval_confidence"] is not None
    assert body["retrieval_confidence"] < 0.99


def test_query_response_includes_confidence_fields(client):
    client.post("/v1/ingest", files=[("files", ("handbook.md", MD_CONTENT, "text/markdown"))])

    resp = client.post("/v1/ask", json={"question": "vacation policy", "top_k": 2})

    body = resp.json()
    assert "retrieval_confidence" in body
    assert "citation_coverage" in body
    assert "citation_coverage_basis" in body
    assert "composite_confidence" in body
    assert "unsupported_citation_markers" in body


def test_dense_only_sources_absent_by_default(client):
    client.post("/v1/ingest", files=[("files", ("handbook.md", MD_CONTENT, "text/markdown"))])

    resp = client.post("/v1/ask", json={"question": "vacation policy", "top_k": 2})

    assert resp.json()["dense_only_sources"] is None


def test_compare_dense_only_populates_a_parallel_sources_list(client):
    client.post("/v1/ingest", files=[("files", ("handbook.md", MD_CONTENT, "text/markdown"))])

    resp = client.post("/v1/ask", json={"question": "vacation policy", "top_k": 2, "compare_dense_only": True})

    body = resp.json()
    assert resp.status_code == 200
    assert body["dense_only_sources"] is not None
    assert len(body["dense_only_sources"]) > 0
    for source in body["dense_only_sources"]:
        assert source["sparse_rank"] is None  # dense-only retrieval never touches BM25


def test_openapi_schema_documents_the_v1_endpoints(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/v1/ask" in paths
    assert "/v1/ingest" in paths
    assert "/v1/documents" in paths
    assert "/v1/documents/{source_document}" in paths
    assert "/health" in paths
    assert "description" in paths["/v1/ask"]["post"]


def test_vector_store_constructed_in_http_mode_when_configured(tmp_path, monkeypatch):
    """create_app should build an HttpClient-backed VectorStore when
    chroma_mode='http', not the default embedded PersistentClient --
    verified by patching chromadb.HttpClient rather than requiring a real
    server for this particular wiring check (the real server is exercised
    directly in tests/test_vector_store.py)."""
    from unittest.mock import MagicMock

    fake_client = MagicMock()
    fake_collection = MagicMock()
    fake_collection.count.return_value = 0
    fake_collection.get.return_value = {"ids": [], "documents": [], "metadatas": []}
    fake_client.get_or_create_collection.return_value = fake_collection
    monkeypatch.setattr("chromadb.HttpClient", lambda host, port: fake_client)

    settings = Settings(chroma_mode="http", chroma_host="fake-chroma-host", chroma_port=9999)
    app = create_app(settings, embedding_client=DeterministicFakeEmbeddingClient(), llm_mode="extractive", sparse_index=SparseIndex())

    assert app.state.vector_store is not None
    fake_client.get_or_create_collection.assert_called_once()
