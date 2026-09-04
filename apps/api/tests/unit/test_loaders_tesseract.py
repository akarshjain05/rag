import pytest
import shutil
from pathlib import Path
from rag_api.adapters.storage.loaders import _load_pdf_pypdfium2
from rag_api.core.settings import get_settings

@pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract is not installed")
def test_tesseract_real_integration(tmp_path):
    import pypdfium2 as pdfium
    from reportlab.pdfgen import canvas
    from PIL import Image
    
    # Create a synthetic PDF with reportlab where we render a page as an image
    pdf_path = tmp_path / "synthetic_scanned.pdf"
    img_path = tmp_path / "dummy.png"
    
    # Create an image with some text
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (400, 200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    # Just draw some text that tesseract can read
    d.text((10,10), "SYNTHETIC OCR TEXT STRING", fill=(0,0,0))
    img.save(img_path)
    
    # Put it in a PDF
    c = canvas.Canvas(str(pdf_path))
    # We do NOT use drawString. We just draw the image so the PDF has NO native text layer!
    c.drawImage(str(img_path), 0, 0, width=400, height=200)
    c.save()
    
    settings = get_settings()
    settings.image_indexing_enabled = True
    settings.image_captioning_enabled = False
    settings.scanned_page_text_threshold = 20
    settings.image_store_backend = "local"
    settings.image_store_path = str(tmp_path / "images")
    
    # Run loader
    doc = _load_pdf_pypdfium2(pdf_path, settings, None)
    
    assert len(doc.pages) == 1
    # Tesseract should have successfully extracted the text
    assert "SYNTHETIC OCR TEXT STRING" in doc.text.upper()
    assert doc.pages[0].extraction_method == "ocr"
    
    # The image is on the page, so it should also extract it as an embedded image
    # But because image_captioning_enabled = False and the image OCR has text, it gets appended as a figure!
    assert "Figure" in doc.text
