"""Three switchable chunking strategies over a `LoadedDocument`.

- fixed_size:       RecursiveCharacterTextSplitter, configurable size/overlap.
                     The baseline every other strategy is judged against.
- structure_aware:  Split on markdown-style headers first (so a chunk never
                     straddles two sections), then recursively sub-split any
                     section still bigger than `structure_max_section_size`.
                     Every chunk carries the heading it fell under.
- semantic:         Split into sentences, embed each one, and cut a new
                     chunk wherever consecutive-sentence cosine similarity
                     drops below a threshold (a topic boundary), subject to
                     a min/max chunk-size safety net. Needs an embedding
                     client — this is the one strategy with an API cost.

For PDFs (`doc.pages` populated), every strategy chunks page-by-page so
`page_number` metadata is always exact; chunks never straddle a page break.
"""
from __future__ import annotations

import re

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from rag_api.adapters.vectorstore.embeddings import EmbeddingClient, cosine_similarity
from rag_api.domain.models import Chunk, ChunkingStrategy, LoadedDocument
from rag_api.domain.chunking.text_utils import split_sentences

_MD_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4"), ("#####", "h5"), ("######", "h6")]
_HEADER_LEVEL_KEYS = [k for _, k in _MD_HEADERS]


def chunk_document(
    doc: LoadedDocument,
    strategy: ChunkingStrategy,
    *,
    fixed_chunk_size: int = 1000,
    fixed_chunk_overlap: int = 150,
    structure_max_section_size: int = 1200,
    semantic_similarity_threshold: float = 0.55,
    semantic_max_chunk_chars: int = 1500,
    semantic_min_chunk_chars: int = 200,
    embedding_client: EmbeddingClient | None = None,
) -> list[Chunk]:
    """Chunk a loaded document with the given strategy. Returns Chunks with
    chunk_index assigned sequentially and page_number set when doc.pages
    is populated (PDF)."""
    if strategy == ChunkingStrategy.SEMANTIC and embedding_client is None:
        raise ValueError("semantic chunking requires an embedding_client")

    def split_one(text: str) -> list[tuple[str, str | None]]:
        if strategy == ChunkingStrategy.FIXED_SIZE:
            return _fixed_size_split(text, fixed_chunk_size, fixed_chunk_overlap)
        if strategy == ChunkingStrategy.STRUCTURE_AWARE:
            return _structure_aware_split(
                text,
                structure_max_section_size,
                embedding_client,
                semantic_similarity_threshold,
                semantic_max_chunk_chars,
                semantic_min_chunk_chars,
            )
        return _semantic_split(
            text,
            embedding_client,  # type: ignore[arg-type]
            semantic_similarity_threshold,
            semantic_max_chunk_chars,
            semantic_min_chunk_chars,
        )

    chunks: list[Chunk] = []
    idx = 0

    if doc.pages:  # PDF: chunk each page separately so page_number stays exact
        for page in doc.pages:
            for text, heading in split_one(page.text):
                if not text.strip():
                    continue
                enriched_text = f"Document: {doc.source_file}\nSection: {heading or 'None'}\n\n{text.strip()}"
                image_ref = None
                content_type = None
                m = re.search(r"> Figure \(Ref: (.*?), Type: (.*?)\):", text)
                if m:
                    image_ref = m.group(1)
                    content_type = m.group(2)
                
                chunks.append(
                    Chunk(
                        text=enriched_text,
                        source_document=doc.source_file,
                        chunking_strategy=strategy.value,
                        chunk_index=idx,
                        section_heading=heading,
                        page_number=page.page_number,
                        image_ref=image_ref,
                        extraction_method=page.extraction_method,
                        content_type=content_type,
                    )
                )
                idx += 1
    else:
        for text, heading in split_one(doc.text):
            if not text.strip():
                continue
            enriched_text = f"Document: {doc.source_file}\nSection: {heading or 'None'}\n\n{text.strip()}"
            image_ref = None
            content_type = None
            m = re.search(r"> Figure \(Ref: (.*?), Type: (.*?)\):", text)
            if m:
                image_ref = m.group(1)
                content_type = m.group(2)

            chunks.append(
                Chunk(
                    text=enriched_text,
                    source_document=doc.source_file,
                    chunking_strategy=strategy.value,
                    chunk_index=idx,
                    section_heading=heading,
                    page_number=None,
                    image_ref=image_ref,
                    content_type=content_type,
                )
            )
            idx += 1

    return chunks


# --------------------------------------------------------------------------
# Strategy 1: fixed-size with overlap
# --------------------------------------------------------------------------
def _fixed_size_split(text: str, chunk_size: int, chunk_overlap: int) -> list[tuple[str, str | None]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [(t, None) for t in splitter.split_text(text) if t.strip()]


# --------------------------------------------------------------------------
# Strategy 2: structure-aware (headers, then recursive sub-split if needed)
# --------------------------------------------------------------------------
def _structure_aware_split(
    text: str,
    max_section_size: int,
    embedding_client: EmbeddingClient | None = None,
    semantic_similarity_threshold: float = 0.55,
    semantic_max_chunk_chars: int = 1500,
    semantic_min_chunk_chars: int = 200,
) -> list[tuple[str, str | None]]:
    if not re.search(r"(?m)^#{1,6}\s", text):
        # No headings in this text (e.g. a plain PDF page) -> fall back to semantic or recursive.
        from rag_api.core.settings import get_settings
        settings = get_settings()
        if settings.structure_aware_semantic_fallback_enabled and embedding_client is not None:
            return _semantic_split(
                text,
                embedding_client,
                semantic_similarity_threshold,
                semantic_max_chunk_chars,
                semantic_min_chunk_chars,
            )
        return _fixed_size_split(text, max_section_size, max_section_size // 8)

    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=_MD_HEADERS, strip_headers=False)
    sections = splitter.split_text(text)

    sub_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_section_size,
        chunk_overlap=min(150, max_section_size // 8),
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    out: list[tuple[str, str | None]] = []
    for section in sections:
        content = section.page_content.strip()
        if not content:
            continue
        heading = _deepest_heading(section.metadata)
        if len(content) <= max_section_size:
            out.append((content, heading))
        else:
            for sub in sub_splitter.split_text(content):
                if sub.strip():
                    out.append((sub, heading))
    return out


def _deepest_heading(metadata: dict) -> str | None:
    heading = None
    for key in _HEADER_LEVEL_KEYS:
        if key in metadata:
            heading = metadata[key]
    return heading


# --------------------------------------------------------------------------
# Strategy 3: semantic (embedding-similarity topic boundaries)
# --------------------------------------------------------------------------
# Sentence splitting lives in app/text_utils.py -- shared with citation-claim
# parsing in app/verification.py rather than duplicated here.


def _semantic_split(
    text: str,
    embedding_client: EmbeddingClient,
    similarity_threshold: float,
    max_chunk_chars: int,
    min_chunk_chars: int,
) -> list[tuple[str, str | None]]:
    sentences = split_sentences(text)
    if not sentences:
        return []
    if len(sentences) == 1:
        return [(sentences[0], None)]

    vectors = embedding_client.embed(sentences)

    chunks: list[str] = []
    current = [sentences[0]]
    current_len = len(sentences[0])

    for i in range(1, len(sentences)):
        sentence = sentences[i]
        similarity = cosine_similarity(vectors[i - 1], vectors[i])
        would_exceed_max = current_len + 1 + len(sentence) > max_chunk_chars
        topic_shift = similarity < similarity_threshold
        reached_min = current_len >= min_chunk_chars

        if would_exceed_max or (topic_shift and reached_min):
            chunks.append(" ".join(current))
            current = [sentence]
            current_len = len(sentence)
        else:
            current.append(sentence)
            current_len += 1 + len(sentence)

    if current:
        chunks.append(" ".join(current))

    return [(c, None) for c in chunks]
