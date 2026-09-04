from __future__ import annotations

from pathlib import Path

import pytest

from rag_api.adapters.storage.loaders import (
    EmptyDocumentError,
    UnsupportedFileTypeError,
    load_document,
    load_documents,
)
from tests.conftest import PDF_PAGE_1_TEXT, PDF_PAGE_2_TEXT


def test_markdown_preserves_headings_and_text(md_path):
    doc = load_document(md_path)
    assert doc.format == "md"
    assert doc.source_file == "sample.md"
    assert doc.pages is None
    assert "## Vacation Policy" in doc.text
    assert "1.5 days per month" in doc.text


def test_plain_text_has_no_pages(txt_path):
    doc = load_document(txt_path)
    assert doc.format == "txt"
    assert doc.pages is None
    assert "quarterly sales performance" in doc.text


def test_html_headings_converted_to_markdown_style(html_path):
    doc = load_document(html_path)
    assert doc.format == "html"
    assert "# Frequently Asked Questions" in doc.text
    assert "## Billing" in doc.text
    assert "## Support" in doc.text
    assert "Invoices are issued on the first of each month." in doc.text


def test_html_strips_script_and_style_tags(html_path):
    doc = load_document(html_path)
    assert "console.log" not in doc.text
    assert "color: red" not in doc.text


def test_pdf_extracts_page_accurate_text(pdf_path):
    doc = load_document(pdf_path)
    assert doc.format == "pdf"
    assert doc.pages is not None
    assert [p.page_number for p in doc.pages] == [1, 2]
    assert doc.pages[0].text == PDF_PAGE_1_TEXT
    assert doc.pages[1].text == PDF_PAGE_2_TEXT
    # full text is the page texts joined
    assert PDF_PAGE_1_TEXT in doc.text
    assert PDF_PAGE_2_TEXT in doc.text


def test_unsupported_extension_raises(tmp_path):
    bad = tmp_path / "sample.csv"
    bad.write_text("hello")
    with pytest.raises(UnsupportedFileTypeError):
        load_document(bad)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_document(tmp_path / "does_not_exist.md")


def test_empty_document_raises(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n\n  ")
    with pytest.raises(EmptyDocumentError):
        load_document(empty)


def test_load_documents_collects_errors_instead_of_raising(tmp_path, md_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("nope")
    loaded, errors = load_documents([md_path, bad, tmp_path / "missing.txt"])
    assert len(loaded) == 1
    assert loaded[0].source_file == "sample.md"
    assert len(errors) == 2
    assert {e["source_file"] for e in errors} == {"bad.csv", "missing.txt"}

def test_docx_preserves_headings_and_tables(docx_path):
    doc = load_document(docx_path)
    assert doc.format == "docx"
    assert doc.pages is None
    assert "# Docx Heading" in doc.text
    assert "This is a paragraph in docx." in doc.text
    assert "## Subheading" in doc.text
    assert "This is a second paragraph." in doc.text
    assert "Header 1 | Header 2" in doc.text
    assert "Val 1 | Val 2" in doc.text


def test_pptx_extracts_slides_as_pages(pptx_path):
    doc = load_document(pptx_path)
    assert doc.format == "pptx"
    assert doc.pages is not None
    assert [p.page_number for p in doc.pages] == [1, 2]
    assert "# Slide 1 Title" in doc.pages[0].text
    assert "Slide 1 Body" in doc.pages[0].text
    assert "# Slide 2 Title" in doc.pages[1].text
    assert "Slide 2 Body" in doc.pages[1].text


def test_xlsx_extracts_sheets_as_markdown_tables(xlsx_path):
    doc = load_document(xlsx_path)
    assert doc.format == "xlsx"
    assert doc.pages is None
    assert "## Sheet1" in doc.text
    assert "Col 1 | Col 2" in doc.text
    assert "--- | ---" in doc.text
    assert "Data 1 | Data 2" in doc.text
    assert "## Sheet2" in doc.text
    assert "A | B | C" in doc.text
    assert "1 | 2 | 3" in doc.text

from unittest.mock import patch
from rag_api.adapters.storage.loaders import _is_heading_candidate, _load_pdf
from rag_api.core.settings import get_settings

def test_pdf_backend_dispatch(tmp_path):
    settings = get_settings()
    settings.pdf_extraction_backend = "pdfplumber"
    settings.image_indexing_enabled = False
    
    with patch("rag_api.adapters.storage.loaders.get_settings", return_value=settings):
        with patch("rag_api.adapters.storage.loaders._load_pdf_pdfplumber") as mock_pdfplumber:
            with patch("rag_api.adapters.storage.loaders._load_pdf_pymupdf") as mock_pymupdf:
                _load_pdf(tmp_path / "dummy.pdf")
                mock_pdfplumber.assert_called_once()
                mock_pymupdf.assert_not_called()

def test_heading_candidate_rejects_bare_numbers():
    assert _is_heading_candidate("325", size_ratio=2.0, is_bold=True, heading_font_ratio=1.15) is False
    assert _is_heading_candidate("...", size_ratio=2.0, is_bold=True, heading_font_ratio=1.15) is False

def test_heading_candidate_accepts_real_heading():
    assert _is_heading_candidate("Chapter 4: Deadlocks", size_ratio=2.0, is_bold=True, heading_font_ratio=1.15) is True
