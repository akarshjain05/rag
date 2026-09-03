from __future__ import annotations

from app.chunking import chunk_document
from app.loaders import load_document
from app.models import ChunkingStrategy, LoadedDocument, PageText


# --------------------------------------------------------------------------
# Fixed-size
# --------------------------------------------------------------------------
def test_fixed_size_respects_chunk_size_and_overlap():
    sentences = [f"Sentence number {i} provides some filler content for chunking." for i in range(40)]
    text = " ".join(sentences)
    doc = LoadedDocument(source_file="long.txt", format="txt", text=text)

    chunks = chunk_document(doc, ChunkingStrategy.FIXED_SIZE, fixed_chunk_size=200, fixed_chunk_overlap=40)

    assert len(chunks) > 1
    for c in chunks:
        assert c.char_count <= 200 + 50  # splitter breaks on separators, so a little slack is expected
        assert c.chunking_strategy == "fixed_size"
        assert c.section_heading is None

    # overlap: consecutive chunks should share some trailing/leading text
    assert chunks[0].text[-20:] in chunks[1].text or chunks[1].text[:20] in chunks[0].text


def test_fixed_size_chunk_ids_are_sequential_and_stable():
    doc = LoadedDocument(source_file="doc.txt", format="txt", text="word " * 500)
    chunks = chunk_document(doc, ChunkingStrategy.FIXED_SIZE, fixed_chunk_size=100, fixed_chunk_overlap=10)
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        assert c.chunk_id == f"doc.txt::fixed_size::{i}"


# --------------------------------------------------------------------------
# Structure-aware
# --------------------------------------------------------------------------
def test_structure_aware_assigns_section_headings(md_path):
    doc = load_document(md_path)
    chunks = chunk_document(doc, ChunkingStrategy.STRUCTURE_AWARE, structure_max_section_size=1200)

    headings = {c.section_heading for c in chunks}
    assert "Vacation Policy" in headings
    assert "Remote Work Policy" in headings

    vacation_chunk = next(c for c in chunks if c.section_heading == "Vacation Policy")
    assert "1.5 days per month" in vacation_chunk.text
    assert vacation_chunk.chunking_strategy == "structure_aware"


def test_structure_aware_sub_splits_oversized_section():
    big_section = "This sentence repeats with small variation number %d. "
    big_body = " ".join(big_section % i for i in range(60))  # a few thousand chars
    text = f"# Report\n\n## Huge Section\n\n{big_body}\n\n## Small Section\n\nShort content here."
    doc = LoadedDocument(source_file="report.md", format="md", text=text)

    chunks = chunk_document(doc, ChunkingStrategy.STRUCTURE_AWARE, structure_max_section_size=500)

    huge_chunks = [c for c in chunks if c.section_heading == "Huge Section"]
    small_chunks = [c for c in chunks if c.section_heading == "Small Section"]

    assert len(huge_chunks) > 1, "oversized section should be sub-split into multiple chunks"
    assert all(c.char_count <= 500 + 50 for c in huge_chunks)
    assert len(small_chunks) == 1, "short section should not be sub-split"


def test_structure_aware_falls_back_when_no_headings_present():
    doc = LoadedDocument(source_file="plain.txt", format="txt", text="No headings anywhere in here. " * 30)
    chunks = chunk_document(doc, ChunkingStrategy.STRUCTURE_AWARE, structure_max_section_size=200)
    assert len(chunks) >= 1
    assert all(c.section_heading is None for c in chunks)


# --------------------------------------------------------------------------
# Semantic
# --------------------------------------------------------------------------
def test_semantic_chunking_splits_on_topic_boundary(fake_embedder):
    pasta_topic = (
        "Boil water in a large pot before adding pasta. "
        "Add a generous amount of salt to the boiling water. "
        "Cook the pasta for eight to ten minutes until tender. "
        "Drain the cooked pasta using a colander in the sink."
    )
    engine_topic = (
        "Check the engine oil level using the dipstick regularly. "
        "Replace the oil filter every scheduled service interval. "
        "Inspect the spark plugs carefully for wear and corrosion. "
        "Replace worn spark plugs promptly to maintain engine performance."
    )
    text = f"{pasta_topic} {engine_topic}"
    doc = LoadedDocument(source_file="mixed.txt", format="txt", text=text)

    chunks = chunk_document(
        doc,
        ChunkingStrategy.SEMANTIC,
        semantic_similarity_threshold=0.55,
        semantic_max_chunk_chars=5000,
        semantic_min_chunk_chars=10,
        embedding_client=fake_embedder,
    )

    assert len(chunks) >= 2, "a clear topic shift should produce at least two chunks"
    # pasta sentences and engine sentences should not both appear packed into a single chunk
    assert not any("pasta" in c.text.lower() and "engine" in c.text.lower() for c in chunks)


def test_semantic_chunking_respects_max_chunk_chars_safety_cap(fake_embedder):
    # highly repetitive -> similarity stays high throughout, so only the
    # max-chars safety net should be creating boundaries
    text = "The quarterly revenue report shows steady growth. " * 30
    doc = LoadedDocument(source_file="repetitive.txt", format="txt", text=text)

    chunks = chunk_document(
        doc,
        ChunkingStrategy.SEMANTIC,
        semantic_similarity_threshold=0.1,  # very low -> topic-shift boundary essentially disabled
        semantic_max_chunk_chars=300,
        semantic_min_chunk_chars=10,
        embedding_client=fake_embedder,
    )

    assert len(chunks) > 1
    for c in chunks:
        assert c.char_count <= 300 + 60


def test_semantic_chunking_requires_embedding_client():
    doc = LoadedDocument(source_file="x.txt", format="txt", text="Some text here.")
    try:
        chunk_document(doc, ChunkingStrategy.SEMANTIC)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "embedding_client" in str(exc)


# --------------------------------------------------------------------------
# PDF: chunks never straddle a page break, page_number always set
# --------------------------------------------------------------------------
def test_pdf_chunks_carry_correct_page_number_and_never_cross_pages():
    doc = LoadedDocument(
        source_file="manual.pdf",
        format="pdf",
        text="Page one body text. Page two body text.",
        pages=[
            PageText(page_number=1, text="Setup instructions go here for the device on page one."),
            PageText(page_number=2, text="Troubleshooting steps go here for the device on page two."),
        ],
    )
    chunks = chunk_document(doc, ChunkingStrategy.FIXED_SIZE, fixed_chunk_size=1000, fixed_chunk_overlap=0)

    assert {c.page_number for c in chunks} == {1, 2}
    for c in chunks:
        if c.page_number == 1:
            assert "page one" in c.text
            assert "page two" not in c.text
        else:
            assert "page two" in c.text
            assert "page one" not in c.text
