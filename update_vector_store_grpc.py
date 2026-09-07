import re
with open("apps/api/src/rag_api/adapters/vectorstore/vector_store.py", "r") as f:
    text = f.read()

bad_init = """    def __init__(
        self,
        persist_dir: str | Path | None = None,
        collection_name: str = "internal_docs",
        *,
        mode: str = "embedded",
        host: str = "qdrant",
        port: int = 6333,
        dense_dimension: int = 768,
    ):
        self.collection_name = collection_name
        
        # Initialize fastembed ONNX runtime immediately on the main thread
        # to prevent OpenMP thread-pool conflicts with PyTorch later.
        self._sparse_model = None
        try:
            from fastembed import SparseTextEmbedding
            self._sparse_model = SparseTextEmbedding("Qdrant/bm25")
        except ImportError:
            import logging
            logging.getLogger(__name__).warning("fastembed is not installed; sparse search disabled.")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to load fastembed sparse model: {e}")
            
        if mode == "http":
            self._client = QdrantClient(host=host, port=port)
        elif mode == "embedded":"""

good_init = """    def __init__(
        self,
        persist_dir: str | Path | None = None,
        collection_name: str = "internal_docs",
        *,
        mode: str = "embedded",
        host: str = "qdrant",
        port: int = 6333,
        grpc_port: int = 6334,
        prefer_grpc: bool = False,
        dense_dimension: int = 768,
    ):
        self.collection_name = collection_name
        
        # Initialize fastembed ONNX runtime immediately on the main thread
        # to prevent OpenMP thread-pool conflicts with PyTorch later.
        self._sparse_model = None
        try:
            from fastembed import SparseTextEmbedding
            self._sparse_model = SparseTextEmbedding("Qdrant/bm25")
        except ImportError:
            import logging
            logging.getLogger(__name__).warning("fastembed is not installed; sparse search disabled.")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to load fastembed sparse model: {e}")
            
        if mode == "http":
            self._client = QdrantClient(host=host, port=port, grpc_port=grpc_port, prefer_grpc=prefer_grpc)
        elif mode == "embedded":"""

text = text.replace(bad_init, good_init)

# add close method
text += """
    def close(self):
        if hasattr(self, "_client") and self._client:
            self._client.close()
"""

with open("apps/api/src/rag_api/adapters/vectorstore/vector_store.py", "w") as f:
    f.write(text)
