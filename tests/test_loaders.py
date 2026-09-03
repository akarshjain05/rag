from __future__ import annotations

from pathlib import Path

import pytest

from app.loaders import (
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
    bad = tmp_path / "sample.docx"
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
    bad = tmp_path / "bad.docx"
    bad.write_text("nope")
    loaded, errors = load_documents([md_path, bad, tmp_path / "missing.txt"])
    assert len(loaded) == 1
    assert loaded[0].source_file == "sample.md"
    assert len(errors) == 2
    assert {e["source_file"] for e in errors} == {"bad.docx", "missing.txt"}
