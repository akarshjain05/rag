import pytest
from pathlib import Path
from rag_api.adapters.vectorstore.sparse_index import SparseIndex, SQLiteFTS5SparseIndex, build_sparse_index

def test_sparse_index_in_memory():
    idx = SparseIndex()
    assert idx.count() == 0
    idx.add_many(["c1", "c2", "c3", "c4", "c5", "c6", "c7"], ["hello world", "test chunk", "another one", "foo", "bar", "baz", "qux"], [{"source_document": "doc1.txt"}, {"source_document": "doc2.txt"}, {"source_document": "doc3.txt"}, {}, {}, {}, {}])
    assert idx.count() == 7
    
    res = idx.query("hello", top_k=5)
    assert len(res) == 1
    assert res[0]["chunk_id"] == "c1"
    
    deleted = idx.delete_source_document("doc1.txt")
    assert deleted == 1
    assert idx.count() == 6
    assert len(idx.query("hello")) == 0
    assert len(idx.query("test")) == 1

def test_sqlite_fts5_sparse_index(tmp_path):
    idx = build_sparse_index("sqlite_fts5", persist_dir=tmp_path)
    assert idx.count() == 0
    
    idx.add_many(["c1", "c2", "c3", "c4", "c5", "c6", "c7"], ["hello world", "test chunk", "another one", "foo", "bar", "baz", "qux"], [{"source_document": "doc1.txt"}, {"source_document": "doc2.txt"}, {"source_document": "doc3.txt"}, {}, {}, {}, {}])
    assert idx.count() == 7
    
    res = idx.query("hello", top_k=5)
    assert len(res) == 1
    assert res[0]["chunk_id"] == "c1"
    
    idx.delete_source_document("doc1.txt")
    assert idx.count() == 6
    assert len(idx.query("hello")) == 0
    
    # Test persistence
    idx2 = build_sparse_index("sqlite_fts5", persist_dir=tmp_path)
    assert idx2.count() == 6
    assert len(idx2.query("test")) == 1

