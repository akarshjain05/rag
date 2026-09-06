from celery import Celery
from rag_api.core.settings import get_settings

settings = get_settings()
celery_app = Celery("rag_api", broker=settings.celery_broker_url, backend=settings.celery_result_backend)

@celery_app.task(bind=True)
def ingest_large_file_task(self, object_key: str, source_filename: str):
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from rag_api.adapters.storage.object_store import ObjectStore
    from rag_api.adapters.vectorstore.embeddings import build_embedding_client
    from rag_api.adapters.vectorstore.vector_store import VectorStore
    from rag_api.services.streaming_ingest import embed_and_index_stream, stream_text_chunks

    s = get_settings()
    store = ObjectStore(
        s.object_store_endpoint or "http://minio:9000", 
        s.object_store_access_key or "minioadmin", 
        s.object_store_secret_key or "minioadminpassword", 
        s.object_store_bucket
    )
    local_path = store.download_to_tmp(object_key)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=s.fixed_chunk_size, chunk_overlap=s.fixed_chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    embedding_client = build_embedding_client(
        provider=s.embedding_provider, openai_model=s.openai_embedding_model,
        openai_api_key=s.openai_api_key, openai_base_url=s.openai_base_url,
        local_model=s.local_embedding_model,
    )
    vector_store = VectorStore(
        s.qdrant_persist_dir, s.collection_name, 
        mode=s.qdrant_mode, host=s.qdrant_host, port=s.qdrant_port,
        dense_dimension=embedding_client.dimension
    )

    report = embed_and_index_stream(
        stream_text_chunks(local_path, splitter, read_block_chars=s.streaming_read_block_chars, tail_overlap_chars=s.streaming_tail_overlap_chars),
        source_document=source_filename,
        embedding_client=embedding_client,
        vector_store=vector_store,
        dedup_threshold=s.dedup_similarity_threshold,
        batch_size=s.streaming_embed_batch_size,
        progress_cb=lambda n: self.update_state(state="PROGRESS", meta={"chunks_processed": n}),
    )
    local_path.unlink(missing_ok=True)
    return vars(report)
