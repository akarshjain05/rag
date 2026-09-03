"""Multi-format document loader.

Accepts markdown, plaintext, HTML and PDF files and normalizes each into a
`LoadedDocument`: clean plaintext plus metadata (source file, section
heading structure, page number for PDFs).

Design note on "section heading" across formats
-------------------------------------------------
Markdown already uses '#'..'######' as its heading convention. To let every
downstream chunker (in particular the structure-aware chunker) treat all
four formats uniformly, HTML headings (<h1>..<h6>) are converted to the same
'#'..'######' markdown-style prefix during normalization. Plaintext has no
heading convention and is passed through unchanged (one untitled section).

PDF is intentionally NOT given synthetic headings. `pypdf`'s text extraction
does not expose font size/weight, so any "is this line a heading" heuristic
built on text alone is unreliable (false positives on short lines, ALL-CAPS
labels, etc.) and would silently corrupt structure-aware chunking. Instead,
PDFs keep their one genuinely reliable structural signal: page number,
tracked per page via `LoadedDocument.pages`.
"""
from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.models import LoadedDocument, PageText

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".html", ".htm", ".pdf"}


class UnsupportedFileTypeError(ValueError):
    pass


class EmptyDocumentError(ValueError):
    pass


def load_document(path: str | Path) -> LoadedDocument:
    """Load and normalize a single file. Raises UnsupportedFileTypeError /
    EmptyDocumentError / FileNotFoundError as appropriate."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")

    suffix = path.suffix.lower()
    if suffix in (".md", ".markdown"):
        doc = _load_markdown(path)
    elif suffix == ".txt":
        doc = _load_text(path)
    elif suffix in (".html", ".htm"):
        doc = _load_html(path)
    elif suffix == ".pdf":
        doc = _load_pdf(path)
    else:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix}' for {path.name}. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    if not doc.text.strip():
        raise EmptyDocumentError(f"{path.name} contains no extractable text")
    return doc


def load_documents(paths: list[str | Path]) -> tuple[list[LoadedDocument], list[dict]]:
    """Load many files. Never raises for a single bad file — collects errors
    instead so one broken upload doesn't abort a whole ingestion batch.
    Returns (loaded_documents, errors) where each error is
    {"source_file": ..., "error": ...}."""
    loaded: list[LoadedDocument] = []
    errors: list[dict] = []
    for p in paths:
        try:
            loaded.append(load_document(p))
        except Exception as exc:  # noqa: BLE001 - intentionally broad, collected not raised
            errors.append({"source_file": str(Path(p).name), "error": str(exc)})
    return loaded, errors


def _load_markdown(path: Path) -> LoadedDocument:
    text = path.read_text(encoding="utf-8", errors="replace")
    return LoadedDocument(source_file=path.name, format="md", text=text)


def _load_text(path: Path) -> LoadedDocument:
    text = path.read_text(encoding="utf-8", errors="replace")
    return LoadedDocument(source_file=path.name, format="txt", text=text)


_HEADING_TAGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}
_BLOCK_TAGS = _HEADING_TAGS.keys() | {"p", "li", "blockquote", "td", "th", "pre", "caption"}


def _load_html(path: Path) -> LoadedDocument:
    raw = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    lines: list[str] = []
    for el in soup.find_all(list(_BLOCK_TAGS)):
        content = " ".join(el.get_text(separator=" ", strip=True).split())
        if not content:
            continue
        prefix = _HEADING_TAGS.get(el.name)
        lines.append(f"{prefix} {content}" if prefix else content)

    text = "\n\n".join(lines)
    return LoadedDocument(source_file=path.name, format="html", text=text)


def _load_pdf(path: Path) -> LoadedDocument:
    reader = PdfReader(str(path))
    pages: list[PageText] = []
    for i, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        if page_text:
            pages.append(PageText(page_number=i, text=page_text))

    full_text = "\n\n".join(p.text for p in pages)
    return LoadedDocument(source_file=path.name, format="pdf", text=full_text, pages=pages)
