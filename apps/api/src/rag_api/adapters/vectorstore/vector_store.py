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
        grpc_port: int = 6334,
        prefer_grpc: bool = False,
        dense_dimension: int = 768,
    ):
        self.collection_name = collection_name
        self.cache_collection = f"{collection_name}_cache"
        
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
        if not self._client.collection_exists(collection_name=self.cache_collection):
            self._client.create_collection(
                collection_name=self.cache_collection,
                vectors_config=models.VectorParams(
                    size=dense_dimension,
                    distance=models.Distance.COSINE
                )
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

    def nearest(self, embedding: list[float], top_k: int = 1, exclude_source_document: str | None = None) -> list[dict]:
        must = [models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to"))]
        must_not = []
        if exclude_source_document:
            must_not.append(models.FieldCondition(key="source_document", match=models.MatchValue(value=exclude_source_document)))
        
        filter_obj = models.Filter(must=must, must_not=must_not) if (must or must_not) else None
        
        res = self._client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            using="dense_jina",
            limit=top_k,
            query_filter=filter_obj
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

    def nearest_batch(self, embeddings: list[list[float]], top_k: int = 1, exclude_source_document: str | None = None) -> list[list[dict]]:
        must = [models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to"))]
        must_not = []
        if exclude_source_document:
            must_not.append(models.FieldCondition(key="source_document", match=models.MatchValue(value=exclude_source_document)))
            
        filter_obj = models.Filter(must=must, must_not=must_not) if (must or must_not) else None

        requests = [
            models.QueryRequest(
                query=emb,
                using="dense_jina",
                limit=top_k,
                filter=filter_obj
            ) for emb in embeddings
        ]
        
        batch_res = self._client.query_batch_points(
            collection_name=self.collection_name,
            requests=requests
        )
        
        out_batch = []
        for res_list in batch_res:
            out = []
            for r in res_list.points:
                out.append({
                    "chunk_id": r.payload["chunk_id"], 
                    "text": r.payload["text"], 
                    "metadata": r.payload, 
                    "similarity": r.score
                })
            out_batch.append(out)
        return out_batch

    def query(self, embedding: list[float], top_k: int = 10, where: dict | None = None, temporal_filter: dict | None = None) -> list[dict]:
        must_conditions = []
        should_conditions = []
        min_should = None
        
        if temporal_filter and "target_date" in temporal_filter:
            from datetime import datetime, timezone
            try:
                dt = datetime.strptime(temporal_filter["target_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                target_ts = int(dt.timestamp())
                must_conditions.append(models.FieldCondition(key="valid_from", range=models.Range(lte=target_ts)))
                should_conditions.extend([
                    models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to")),
                    models.FieldCondition(key="valid_to", range=models.Range(gt=target_ts))
                ])
                min_should = 1
            except Exception:
                must_conditions.append(models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to")))
        else:
            must_conditions.append(models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to")))

        if where:
            for k, v in where.items():
                if isinstance(v, list):
                    must_conditions.append(models.FieldCondition(key=k, match=models.MatchAny(any=v)))
                else:
                    must_conditions.append(models.FieldCondition(key=k, match=models.MatchValue(value=v)))
                    
        filter_kwargs = {"must": must_conditions}
        if should_conditions:
            filter_kwargs["should"] = should_conditions
            filter_kwargs["min_should"] = min_should
            
        filter_obj = models.Filter(**filter_kwargs)
            
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
        
    def hybrid_search(self, query_text: str, dense_vector: list[float], top_k: int = 25, where: dict | None = None, prefetch_limit: int = 60, temporal_filter: dict | None = None) -> list[dict]:
        must_conditions = []
        should_conditions = []
        min_should = None
        
        if temporal_filter and "target_date" in temporal_filter:
            from datetime import datetime, timezone
            try:
                dt = datetime.strptime(temporal_filter["target_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                target_ts = int(dt.timestamp())
                must_conditions.append(models.FieldCondition(key="valid_from", range=models.Range(lte=target_ts)))
                should_conditions.extend([
                    models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to")),
                    models.FieldCondition(key="valid_to", range=models.Range(gt=target_ts))
                ])
                min_should = 1
            except Exception:
                must_conditions.append(models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to")))
        else:
            must_conditions.append(models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to")))
        if where:
            for k, v in where.items():
                if isinstance(v, list):
                    must_conditions.append(models.FieldCondition(key=k, match=models.MatchAny(any=v)))
                else:
                    must_conditions.append(models.FieldCondition(key=k, match=models.MatchValue(value=v)))
                    
        filter_kwargs = {"must": must_conditions}
        if should_conditions:
            filter_kwargs["should"] = should_conditions
            filter_kwargs["min_should"] = min_should
            
        filter_obj = models.Filter(**filter_kwargs)
            
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
        self._client.delete(collection_name=self.collection_name, points_selector=filter_obj, wait=True)
        
        # Also wipe any cached queries that relied on this document
        try:
            self.semantic_cache_invalidate(source_document)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to invalidate semantic cache for {source_document}: {e}")
            
        return count

    def sparse_query(self, query_text: str, top_k: int = 10, where: dict | None = None, temporal_filter: dict | None = None) -> list[dict]:
        must_conditions = []
        should_conditions = []
        min_should = None
        
        if temporal_filter and "target_date" in temporal_filter:
            from datetime import datetime, timezone
            try:
                dt = datetime.strptime(temporal_filter["target_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                target_ts = int(dt.timestamp())
                must_conditions.append(models.FieldCondition(key="valid_from", range=models.Range(lte=target_ts)))
                should_conditions.extend([
                    models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to")),
                    models.FieldCondition(key="valid_to", range=models.Range(gt=target_ts))
                ])
                min_should = 1
            except Exception:
                must_conditions.append(models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to")))
        else:
            must_conditions.append(models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to")))

        if where:
            for k, v in where.items():
                if isinstance(v, list):
                    must_conditions.append(models.FieldCondition(key=k, match=models.MatchAny(any=v)))
                else:
                    must_conditions.append(models.FieldCondition(key=k, match=models.MatchValue(value=v)))
                    
        filter_kwargs = {"must": must_conditions}
        if should_conditions:
            filter_kwargs["should"] = should_conditions
            filter_kwargs["min_should"] = min_should
            
        filter_obj = models.Filter(**filter_kwargs)
            
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

    def semantic_cache_get(self, query_vector: list[float], threshold: float = 0.95, ttl_seconds: int = 604800, conversation_id: str | None = None, document_filter: list[str] | None = None, chunking_strategy: str | None = None) -> dict | None:
        import time
        must = []
        
        must.append(models.FieldCondition(key="conversation_id", match=models.MatchValue(value=conversation_id or "")))
        must.append(models.FieldCondition(key="chunking_strategy", match=models.MatchValue(value=chunking_strategy or "")))
        
        if document_filter:
            must.append(models.FieldCondition(key="document_filter", match=models.MatchAny(any=document_filter)))
        else:
            must.append(models.IsEmptyCondition(is_empty=models.PayloadField(key="document_filter")))
            
        res = self._client.query_points(
            collection_name=self.cache_collection,
            query=query_vector,
            limit=1,
            score_threshold=threshold,
            query_filter=models.Filter(must=must) if must else None
        )
        if not res.points:
            return None
            
        point = res.points[0]
        # Time-To-Live (TTL) Validation
        if time.time() - point.payload.get("timestamp", 0) > ttl_seconds:
            return None # Cache expired
            
        return point.payload["response"]

    def semantic_cache_set(self, query_text: str, query_vector: list[float], response: dict, conversation_id: str | None = None, document_filter: list[str] | None = None, chunking_strategy: str | None = None) -> None:
        import uuid
        import time
        
        # Extract unique source documents from the response to allow document-level cache invalidation
        source_docs = []
        if "sources" in response:
            source_docs = list(set([s.get("source_document") for s in response["sources"] if s.get("source_document")]))
            
        self._client.upsert(
            collection_name=self.cache_collection,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=query_vector,
                    payload={
                        "original_query": query_text,
                        "response": response,
                        "timestamp": time.time(),
                        "source_documents": source_docs,
                        "conversation_id": conversation_id or "",
                        "document_filter": document_filter or [],
                        "chunking_strategy": chunking_strategy or "",
                    }
                )
            ]
        )

    def semantic_cache_invalidate(self, source_document: str) -> int:
        """Wipes all cached queries that relied on the specified source document."""
        filter_obj = models.Filter(
            must=[
                models.FieldCondition(
                    key="source_documents",
                    match=models.MatchValue(value=source_document)
                )
            ]
        )
        count = self._client.count(collection_name=self.cache_collection, count_filter=filter_obj).count
        self._client.delete(collection_name=self.cache_collection, points_selector=filter_obj, wait=True)
        return count

    def expire_source_document(self, source_document: str, current_time: int) -> int:
        """Updates the valid_to timestamp of all active chunks for a document."""
        filter_obj = models.Filter(
            must=[
                models.FieldCondition(key="source_document", match=models.MatchValue(value=source_document)),
                models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to"))
            ]
        )
        count = self._client.count(collection_name=self.collection_name, count_filter=filter_obj).count
        
        # We only need to set payload if there are points
        if count > 0:
            self._client.set_payload(
                collection_name=self.collection_name,
                payload={"valid_to": current_time},
                points=filter_obj,
                wait=True
            )
            # Also wipe semantic cache because the old doc is obsolete
            try:
                self.semantic_cache_invalidate(source_document)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to invalidate semantic cache for {source_document}: {e}")
        return count

    def close(self):
        if hasattr(self, "_client") and self._client:
            self._client.close()
