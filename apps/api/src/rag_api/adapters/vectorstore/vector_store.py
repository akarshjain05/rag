from __future__ import annotations
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http import models

class VectorStore:
    def __init__(
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
        elif mode == "embedded":
            if persist_dir is None:
                raise ValueError("persist_dir is required when mode='embedded'")
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            self._client = QdrantClient(path=str(persist_dir))
        else:
            raise ValueError(f"Unknown VectorStore mode: {mode!r}")

        # Ensure collection exists with both dense and sparse configurations
        if not self._client.collection_exists(collection_name=self.collection_name):
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense_jina": models.VectorParams(
                        size=dense_dimension,
                        distance=models.Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    "sparse_bm25": models.SparseVectorParams(
                        modifier=models.Modifier.IDF
                    )
                }
            )


    def count(self) -> int:
        return self._client.get_collection(self.collection_name).points_count

    def add(self, chunk_id: str, embedding: list[float], text: str, metadata: dict) -> None:
        self.add_many([chunk_id], [embedding], [text], [metadata])

    def add_many(self, chunk_ids: list[str], embeddings: list[list[float]], texts: list[str], metadatas: list[dict]) -> None:
        if not chunk_ids:
            return
            
        import uuid
        
        def to_uuid(cid: str) -> str:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, cid))
            
        try:
            sparse_embeddings = list(self._sparse_model.embed(texts))
        except (ImportError, AttributeError):
            sparse_embeddings = [None] * len(texts)
            
        points = []
        for cid, emb, txt, meta, sp_emb in zip(chunk_ids, embeddings, texts, metadatas, sparse_embeddings):
            meta["text"] = txt
            meta["chunk_id"] = cid
            
            vector_dict = {"dense_jina": emb}
            if sp_emb is not None:
                vector_dict["sparse_bm25"] = models.SparseVector(
                    indices=sp_emb.indices.tolist(),
                    values=sp_emb.values.tolist()
                )
                
            points.append(
                models.PointStruct(
                    id=to_uuid(cid),
                    payload=meta,
                    vector=vector_dict
                )
            )
            
        # Add the points with their dense AND sparse vectors in one go!
        self._client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    def nearest(self, embedding: list[float], top_k: int = 1) -> list[dict]:
        res = self._client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            using="dense_jina",
            limit=top_k
        ).points
        out = []
        for r in res:
            out.append({
                "chunk_id": r.payload["chunk_id"], 
                "text": r.payload["text"], 
                "metadata": r.payload, 
                "similarity": r.score
            })
        return out

    def query(self, embedding: list[float], top_k: int = 10, where: dict | None = None) -> list[dict]:
        # Basic filtering map
        filter_obj = None
        if where:
            conditions = []
            for k, v in where.items():
                if isinstance(v, list):
                    conditions.append(models.FieldCondition(key=k, match=models.MatchAny(any=v)))
                else:
                    conditions.append(models.FieldCondition(key=k, match=models.MatchValue(value=v)))
            filter_obj = models.Filter(must=conditions)
            
        res = self._client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            using="dense_jina",
            query_filter=filter_obj,
            limit=top_k
        ).points
        out = []
        for r in res:
            out.append({
                "chunk_id": r.payload["chunk_id"], 
                "text": r.payload["text"], 
                "metadata": r.payload, 
                "similarity": r.score
            })
        return out
        
    def hybrid_search(self, query_text: str, dense_vector: list[float], top_k: int = 25, where: dict | None = None, prefetch_limit: int = 60) -> list[dict]:
        filter_obj = None
        if where:
            conditions = []
            for k, v in where.items():
                if isinstance(v, list):
                    conditions.append(models.FieldCondition(key=k, match=models.MatchAny(any=v)))
                else:
                    conditions.append(models.FieldCondition(key=k, match=models.MatchValue(value=v)))
            filter_obj = models.Filter(must=conditions)
            
        if not getattr(self, "_sparse_model", None):
            return self.query(dense_vector, top_k=top_k, where=where)
            
        sp_emb = list(self._sparse_model.embed([query_text]))[0]
            
        response = self._client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sp_emb.indices.tolist(),
                        values=sp_emb.values.tolist()
                    ),
                    using="sparse_bm25",
                    limit=prefetch_limit,
                    filter=filter_obj,
                ),
                models.Prefetch(
                    query=dense_vector,
                    using="dense_jina",
                    limit=prefetch_limit,
                    filter=filter_obj,
                )
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k
        )
        
        out = []
        for r in response.points:
            out.append({
                "chunk_id": r.payload["chunk_id"], 
                "text": r.payload["text"], 
                "metadata": r.payload, 
                "similarity": r.score
            })
        return out

    def get_all(self) -> list[dict]:
        res, _ = self._client.scroll(collection_name=self.collection_name, limit=10000)
        out = []
        for r in res:
            out.append({"chunk_id": r.payload["chunk_id"], "text": r.payload["text"], "metadata": r.payload})
        return out

    def list_source_documents(self) -> list[str]:
        seen = {}
        for row in self.get_all():
            seen.setdefault(row["metadata"].get("source_document", "unknown"), None)
        return list(seen.keys())

    def delete_source_document(self, source_document: str) -> int:
        filter_obj = models.Filter(
            must=[models.FieldCondition(key="source_document", match=models.MatchValue(value=source_document))]
        )
        count = self._client.count(collection_name=self.collection_name, count_filter=filter_obj).count
        self._client.delete(collection_name=self.collection_name, points_selector=filter_obj)
        return count

    def sparse_query(self, query_text: str, top_k: int = 10, where: dict | None = None) -> list[dict]:
        filter_obj = None
        if where:
            conditions = []
            for k, v in where.items():
                if isinstance(v, list):
                    conditions.append(models.FieldCondition(key=k, match=models.MatchAny(any=v)))
                else:
                    conditions.append(models.FieldCondition(key=k, match=models.MatchValue(value=v)))
            filter_obj = models.Filter(must=conditions)
            
        if not getattr(self, "_sparse_model", None):
            return []
            
        sp_emb = list(self._sparse_model.embed([query_text]))[0]
            
        res = self._client.query_points(
            collection_name=self.collection_name,
            query=models.SparseVector(
                indices=sp_emb.indices.tolist(),
                values=sp_emb.values.tolist()
            ),
            using="sparse_bm25",
            limit=top_k,
            query_filter=filter_obj,
            with_payload=True
        )
        out = []
        for point in res.points:
            out.append({
                "chunk_id": point.payload.get("chunk_id", str(point.id)),
                "text": point.payload.get("text", ""),
                "metadata": point.payload,
                "similarity": point.score
            })
        return out
