from __future__ import annotations

import shutil
import subprocess
import urllib.request

import pytest


def test_empty_store_count_and_queries(vector_store):
    assert vector_store.count() == 0
    assert vector_store.nearest([1.0, 0.0, 0.0], top_k=1) == []
    assert vector_store.query([1.0, 0.0, 0.0], top_k=5) == []
    assert vector_store.get_all() == []
    assert vector_store.list_source_documents() == []


def test_add_and_query_returns_nearest_first(vector_store):
    vector_store.add("a", [1.0, 0.0, 0.0], "doc a text", {"source_document": "x.md"})
    vector_store.add("b", [0.0, 1.0, 0.0], "doc b text", {"source_document": "y.md"})
    vector_store.add("c", [0.9, 0.1, 0.0], "doc c text", {"source_document": "x.md"})

    assert vector_store.count() == 3

    results = vector_store.query([1.0, 0.0, 0.0], top_k=3)
    assert results[0]["chunk_id"] == "a"  # exact match should rank first
    assert results[0]["similarity"] > results[-1]["similarity"]


def test_query_top_k_caps_at_collection_size(vector_store):
    vector_store.add("a", [1.0, 0.0], "a", {"source_document": "x"})
    results = vector_store.query([1.0, 0.0], top_k=50)
    assert len(results) == 1


def test_query_with_metadata_filter(vector_store):
    vector_store.add("a", [1.0, 0.0], "a", {"source_document": "x", "chunking_strategy": "fixed_size"})
    vector_store.add("b", [0.99, 0.1], "b", {"source_document": "x", "chunking_strategy": "semantic"})

    results = vector_store.query([1.0, 0.0], top_k=5, where={"chunking_strategy": "semantic"})
    assert len(results) == 1
    assert results[0]["chunk_id"] == "b"


def test_add_many_and_get_all(vector_store):
    vector_store.add_many(
        chunk_ids=["a", "b"],
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
        texts=["text a", "text b"],
        metadatas=[{"source_document": "x"}, {"source_document": "y"}],
    )
    rows = vector_store.get_all()
    assert {r["chunk_id"] for r in rows} == {"a", "b"}


def test_list_source_documents_deduplicates(vector_store):
    vector_store.add("a", [1.0, 0.0], "t1", {"source_document": "x.md"})
    vector_store.add("b", [0.0, 1.0], "t2", {"source_document": "x.md"})
    vector_store.add("c", [1.0, 1.0], "t3", {"source_document": "y.md"})
    assert set(vector_store.list_source_documents()) == {"x.md", "y.md"}


def test_delete_source_document_removes_only_matching_chunks(vector_store):
    vector_store.add("a", [1.0, 0.0], "t1", {"source_document": "x.md"})
    vector_store.add("b", [0.0, 1.0], "t2", {"source_document": "y.md"})

    deleted = vector_store.delete_source_document("x.md")

    assert deleted == 1
    assert vector_store.count() == 1
    assert vector_store.list_source_documents() == ["y.md"]


def test_persistence_across_instances(tmp_path):
    from rag_api.adapters.vectorstore.vector_store import VectorStore

    persist_dir = tmp_path / "chroma"
    store1 = VectorStore(persist_dir=persist_dir, collection_name="persisted")
    store1.add("a", [1.0, 0.0], "hello", {"source_document": "x"})

    store2 = VectorStore(persist_dir=persist_dir, collection_name="persisted")
    assert store2.count() == 1
    assert store2.get_all()[0]["chunk_id"] == "a"


def test_embedded_mode_requires_persist_dir():
    from rag_api.adapters.vectorstore.vector_store import VectorStore

    with pytest.raises(ValueError, match="persist_dir is required"):
        VectorStore(mode="embedded")


def test_unknown_mode_raises():
    from rag_api.adapters.vectorstore.vector_store import VectorStore

    with pytest.raises(ValueError, match="Unknown VectorStore mode"):
        VectorStore(mode="not-a-real-mode")


@pytest.mark.skipif(shutil.which("chroma") is None, reason="chroma server binary not on PATH")
def test_http_mode_against_a_real_local_chroma_server(tmp_path):
    """Not mocked: launches a real `chroma run` server as a subprocess and
    talks to it over HTTP, the same way docker-compose's chromadb service
    is reached in the "http" deployment mode. Confirms VectorStore's HTTP
    path is genuinely wired correctly, not just that construction doesn't
    raise."""
    import time
    from rag_api.adapters.vectorstore.vector_store import VectorStore

    port = 8901
    data_dir = tmp_path / "chroma_server_data"
    data_dir.mkdir()
    proc = subprocess.Popen(
        ["chroma", "run", "--path", str(data_dir), "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 15
        ready = False
        while time.time() < deadline:
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v2/heartbeat", timeout=1).status == 200:
                    ready = True
                    break
            except Exception:
                time.sleep(0.5)
        assert ready, "chroma server did not become healthy in time"

        store = VectorStore(collection_name="http_test", mode="http", host="127.0.0.1", port=port)
        assert store.count() == 0

        store.add("a", [1.0, 0.0, 0.0], "doc a", {"source_document": "x"})
        store.add("b", [0.0, 1.0, 0.0], "doc b", {"source_document": "y"})
        assert store.count() == 2

        results = store.query([0.9, 0.1, 0.0], top_k=2)
        assert results[0]["chunk_id"] == "a"

        deleted = store.delete_source_document("x")
        assert deleted == 1
        assert store.count() == 1
    finally:
        proc.terminate()
        proc.wait(timeout=10)
