import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from rag_api.adapters.storage.loaders import _load_pdf_pypdfium2
from rag_api.core.settings import get_settings
from rag_api.domain.models import LoadedDocument

@pytest.fixture
def dummy_settings():
    settings = get_settings()
    settings.image_indexing_enabled = True
    settings.image_captioning_enabled = True
    settings.scanned_page_text_threshold = 20
    settings.image_store_backend = "local"
    return settings

def test_ocr_vs_caption_branching(dummy_settings, tmp_path, monkeypatch):
    import pytest
    pytest.importorskip("pytesseract")
    mock_ocr = MagicMock()
    monkeypatch.setattr("pytesseract.image_to_string", mock_ocr)
    mock_pdf = MagicMock()
    monkeypatch.setattr("pypdfium2.PdfDocument", mock_pdf)
    pytest.importorskip("pytesseract")
    pytest.importorskip('pytesseract')
    dummy_settings.image_store_path = str(tmp_path)
    # Mock PDF with 2 pages: one scanned page, one page with embedded image
    mock_doc = MagicMock()
    mock_pdf.return_value = mock_doc
    mock_doc.__len__.return_value = 2
    
    # Page 1: Scanned page
    page1 = MagicMock()
    page1.get_textpage().get_text_bounded.return_value = "Short"
    mock_bitmap = MagicMock()
    mock_bitmap.to_pil.return_value = MagicMock()
    page1.render.return_value = mock_bitmap
    page1.get_objects.return_value = []
    
    # Page 2: Embedded Image
    page2 = MagicMock()
    page2.get_textpage().get_text_bounded.return_value = "Normal text that is long enough to bypass scanned check."
    mock_img_obj = MagicMock()
    import pypdfium2
    mock_img_obj.__class__ = pypdfium2.PdfImage
    mock_img_bitmap = MagicMock()
    mock_pil = MagicMock()
    mock_pil.save = MagicMock()
    mock_img_bitmap.to_pil.return_value = mock_pil
    mock_img_obj.get_bitmap.return_value = mock_img_bitmap
    page2.get_objects.return_value = [mock_img_obj]
    
    mock_doc.__getitem__.side_effect = [page1, page2]
    
    # Tesseract returns long text for page1 (so it's extracted via OCR)
    # Tesseract returns short text for page2 image (so it goes to LLM captioning)
    mock_ocr.side_effect = ["This is a fully scanned page with lots of text.", "Short img"]
    
    mock_llm = MagicMock()
    mock_llm.describe_image.return_value = "A beautiful caption from LLM."
    
    doc = _load_pdf_pypdfium2(Path("test.pdf"), dummy_settings, mock_llm, None)
    
    assert doc.pages[0].extraction_method == "ocr"
    assert "This is a fully scanned page with lots of text." in doc.pages[0].text
    
    assert doc.pages[1].extraction_method == "native"
    assert "Normal text" in doc.pages[1].text
    assert "<!--IMG:no_store-->" in doc.pages[1].text
    # removed
    assert "A beautiful caption from LLM." in doc.pages[1].text
    
    mock_llm.describe_image.assert_called_once()
