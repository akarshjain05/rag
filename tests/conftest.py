"""Shared pytest fixtures.

The PDF fixture is generated on the fly with reportlab (a dev-only
dependency) rather than committed as a binary file, so the test suite has
no binary fixtures and the PDF's exact page contents always match what the
tests assert against.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.embeddings import DeterministicFakeEmbeddingClient
from app.sparse_index import SparseIndex
from app.vector_store import VectorStore

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def md_path() -> Path:
    return FIXTURES_DIR / "sample.md"


@pytest.fixture
def txt_path() -> Path:
    return FIXTURES_DIR / "sample.txt"


@pytest.fixture
def html_path() -> Path:
    return FIXTURES_DIR / "sample.html"


PDF_PAGE_1_TEXT = "Onboarding new employees begins with an equipment request submitted to IT."
PDF_PAGE_2_TEXT = "Offboarding departing employees requires revoking all system access within 24 hours."


@pytest.fixture
def pdf_path(tmp_path: Path) -> Path:
    from reportlab.pdfgen import canvas

    path = tmp_path / "sample.pdf"
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, PDF_PAGE_1_TEXT)
    c.showPage()
    c.drawString(72, 720, PDF_PAGE_2_TEXT)
    c.showPage()
    c.save()
    return path


@pytest.fixture
def fake_embedder() -> DeterministicFakeEmbeddingClient:
    return DeterministicFakeEmbeddingClient(dimension=128)


@pytest.fixture
def vector_store(tmp_path: Path) -> VectorStore:
    return VectorStore(persist_dir=tmp_path / "chroma", collection_name="test_collection")


@pytest.fixture
def sparse_index() -> SparseIndex:
    return SparseIndex()
