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
    ):
        self.collection_name = collection_name
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
                        size=768,  # Jina v2 base en size
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
        
        # FastEmbed requires generating sparse vectors locally before upload if using regular upload,
        # OR we can just use the fastembed integrated methods.
        # However, for simplicity, we will just use QdrantClient.add which automatically uses FastEmbed 
        # for sparse vectors if configured correctly!
        
        # Qdrant requires UUID or integer IDs
        def to_uuid(cid: str) -> str:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, cid))
            
        try:
            from fastembed import SparseTextEmbedding
            sparse_model = SparseTextEmbedding("Qdrant/bm25")
            sparse_embeddings = list(sparse_model.embed(texts))
        except Exception:
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
        res = self._client.search(
            collection_name=self.collection_name,
            query_vector=models.NamedVector(
                name="dense_jina",
                vector=embedding
            ),
            limit=top_k
        )
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
                conditions.append(models.FieldCondition(key=k, match=models.MatchValue(value=v)))
            filter_obj = models.Filter(must=conditions)
            
        res = self._client.search(
            collection_name=self.collection_name,
            query_vector=models.NamedVector(
                name="dense_jina",
                vector=embedding
            ),
            query_filter=filter_obj,
            limit=top_k
        )
        out = []
        for r in res:
            out.append({
                "chunk_id": r.payload["chunk_id"], 
                "text": r.payload["text"], 
                "metadata": r.payload, 
                "similarity": r.score
            })
        return out
        
    def hybrid_search(self, query_text: str, dense_vector: list[float], top_k: int = 25, where: dict | None = None) -> list[dict]:
        filter_obj = None
        if where:
            conditions = []
            for k, v in where.items():
                conditions.append(models.FieldCondition(key=k, match=models.MatchValue(value=v)))
            filter_obj = models.Filter(must=conditions)
            
        from fastembed import SparseTextEmbedding
        sparse_model = SparseTextEmbedding("Qdrant/bm25")
        sp_emb = list(sparse_model.embed([query_text]))[0]
            
        response = self._client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sp_emb.indices.tolist(),
                        values=sp_emb.values.tolist()
                    ),
                    using="sparse_bm25",
                    limit=60,
                    filter=filter_obj,
                ),
                models.Prefetch(
                    query=dense_vector,
                    using="dense_jina",
                    limit=60,
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
        self._client.delete(collection_name=self.collection_name, points_selector=filter_obj)
        return 1
