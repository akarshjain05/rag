"""End-to-end ingestion pipeline: load -> chunk -> embed -> dedup -> index.

One embedding API call per file (all of a file's chunks embedded in a single
batch request), then a sequential per-chunk dedup check against the vector
store's *current* contents — so a duplicate is caught whether it matches a
chunk from a previous run or one inserted earlier in this very call.
"""
from __future__ import annotations
from rag_api.core.logging import log

from pathlib import Path

from rag_api.domain.chunking.chunking import chunk_document
from rag_api.adapters.storage.dedup import check_duplicate, check_duplicate_batch
from rag_api.adapters.vectorstore.embeddings import EmbeddingClient
from rag_api.adapters.storage.loaders import load_document
from rag_api.domain.models import ChunkingStrategy, IngestReport
from rag_api.adapters.vectorstore.vector_store import VectorStore


class IngestionPipeline:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_store: VectorStore,
        
        llm_client = None,
        image_store = None,
        *,
        default_strategy: ChunkingStrategy = ChunkingStrategy.STRUCTURE_AWARE,
        fixed_chunk_size: int = 1000,
        fixed_chunk_overlap: int = 150,
        structure_max_section_size: int = 1200,
        semantic_similarity_threshold: float = 0.55,
        semantic_max_chunk_chars: int = 1500,
        semantic_min_chunk_chars: int = 200,
        dedup_similarity_threshold: float = 0.95,
    ):
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        
        self.llm_client = llm_client
        self.image_store = image_store
        self.default_strategy = default_strategy
        self.fixed_chunk_size = fixed_chunk_size
        self.fixed_chunk_overlap = fixed_chunk_overlap
        self.structure_max_section_size = structure_max_section_size
        self.semantic_similarity_threshold = semantic_similarity_threshold
        self.semantic_max_chunk_chars = semantic_max_chunk_chars
        self.semantic_min_chunk_chars = semantic_min_chunk_chars
        self.dedup_similarity_threshold = dedup_similarity_threshold

    def ingest_file(
        self,
        path: str | Path,
        strategy: ChunkingStrategy | None = None,
        progress_callback = None,
    ) -> IngestReport:
        strategy = strategy or self.default_strategy
        source_name = Path(path).name

        try:
            if progress_callback: progress_callback(10, f"Loading {source_name}...")
            doc = load_document(path, llm_client=self.llm_client, image_store=self.image_store)
        except Exception as exc:  # noqa: BLE001 - reported, not raised, so batches survive one bad file
            return IngestReport(source_file=source_name, chunking_strategy=strategy.value, error=f"Loading failed: {str(exc)}")

        try:
            if progress_callback: progress_callback(20, "Chunking document...")
            chunks, skipped_low_quality = chunk_document(
                doc,
                strategy,
                fixed_chunk_size=self.fixed_chunk_size,
                fixed_chunk_overlap=self.fixed_chunk_overlap,
                structure_max_section_size=self.structure_max_section_size,
                semantic_similarity_threshold=self.semantic_similarity_threshold,
                semantic_max_chunk_chars=self.semantic_max_chunk_chars,
                semantic_min_chunk_chars=self.semantic_min_chunk_chars,
                embedding_client=self.embedding_client if strategy in (ChunkingStrategy.SEMANTIC, ChunkingStrategy.STRUCTURE_AWARE) else None,
            )

            import concurrent.futures

            # --- CONTEXTUAL RETRIEVAL PREPROCESSING (Anthropic Method) ---
            if self.llm_client and chunks:
                if progress_callback: progress_callback(30, "Generating Contextual Summaries...")
                print(f"Generating Contextual Retrieval summaries for {len(chunks)} chunks in {doc.source_file} (leveraging Prompt Caching)...")
                
                # Format the massive document as the system prompt and explicitly add Anthropic's cache_control flag
                system_prompt = [
                    {
                        "type": "text",
                        "text": "You are a specialized preprocessing agent. Generate a concise context summary to improve search retrieval."
                    },
                    {
                        "type": "text",
                        "text": f"<document>\n{doc.text[:250000]}\n</document>\n\n",
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
                
                def situate_chunk(c):
                    prompt = f"Here is the chunk we want to situate within the whole document:\n<chunk>\n{c.text}\n</chunk>\n\nPlease give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."
                    try:
                        context = self.llm_client.generate(system_prompt, prompt).strip()
                        # Prepend the context to the chunk, so it is embedded, indexed by BM25, and visible to the final Generator LLM
                        c.text = f"[{context}]\n\n{c.text}"
                    except Exception as e:
                        print(f"Warning: Context generation failed for chunk {c.chunk_id} - {e}")
                    return c
                    
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    chunks = list(executor.map(situate_chunk, chunks))
            # -------------------------------------------------------------

            report = IngestReport(
                source_file=doc.source_file,
                chunking_strategy=strategy.value,
                chunks_created=len(chunks),
                chunks_skipped_low_quality=skipped_low_quality
            )
            if not chunks:
                return report

            if progress_callback: progress_callback(50, f"Generating {len(chunks)} Jina Embeddings...")
            embeddings = self.embedding_client.embed([c.text for c in chunks])

            if progress_callback: progress_callback(80, "Checking for duplicates & indexing into Qdrant...")
            inserted_ids = []
            inserted_texts = []
            inserted_metas = []
            inserted_embeddings = []
            
            # Batch dedup check
            dedups = check_duplicate_batch(embeddings, self.vector_store, threshold=self.dedup_similarity_threshold)
            
            for chunk, embedding, dedup in zip(chunks, embeddings, dedups):
                if dedup.is_duplicate:
                    report.duplicates_skipped += 1
                    report.duplicate_of.append(dedup.duplicate_of)
                    continue
                inserted_ids.append(chunk.chunk_id)
                inserted_texts.append(chunk.text)
                inserted_metas.append(chunk.metadata())
                inserted_embeddings.append(embedding)
                report.chunks_inserted += 1
                
            if inserted_ids:
                self.vector_store.add_many(inserted_ids, inserted_embeddings, inserted_texts, inserted_metas)



            return report
        except Exception as exc:
            return IngestReport(source_file=source_name, chunking_strategy=strategy.value, error=f"Ingestion failed: {str(exc)}")

    def ingest_files(self, paths: list[str | Path], strategy: ChunkingStrategy | None = None, progress_callback = None) -> list[IngestReport]:
        reports = []
        total = len(paths)
        for i, p in enumerate(paths):
            def local_cb(pct, msg):
                if progress_callback:
                    # scale progress to the current file
                    base = (i / total) * 100
                    scaled = base + (pct / total)
                    progress_callback(int(scaled), msg)
            reports.append(self.ingest_file(p, strategy, progress_callback=local_cb))
        if progress_callback: progress_callback(100, "Complete!")
        return reports
