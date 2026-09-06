"""Small text utilities shared across modules that would otherwise each
reimplement a sentence splitter (semantic chunking, citation-claim parsing).

The splitter is regex-based (punctuation + following capital letter/digit),
not a real sentence tokenizer, so it will mis-split on abbreviations
(`e.g.`, `Dr.`) in adversarial text. Documented as a known limitation in the
README rather than pulling in spaCy/nltk for what both call sites treat as
a "good enough" boundary, not a hard requirement.
"""
from __future__ import annotations

import re

_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'\u201c])')


def split_sentences(text: str) -> list[str]:
    """Paragraph breaks are treated as hard sentence boundaries too, then
    each paragraph is split on punctuation followed by a capital
    letter/digit/quote."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    sentences: list[str] = []
    for para in paragraphs:
        para = re.sub(r"\s+", " ", para).strip()
        para = re.sub(r"^#{1,6}\s+", "", para)  # strip a leading markdown heading marker
        if not para:
            continue
        sentences.extend(s.strip() for s in _SENTENCE_SPLIT_RE.split(para) if s.strip())
    return sentences

def estimate_tokens(text: str) -> int:
    """Fast, provider-agnostic heuristic (~4 chars/token for English
    prose). Exact tokenization isn't needed to decide whether ~440k
    tokens will blow a 128k context window -- it's needed to decide
    *before spending an API call finding out*."""
    return len(text) // 4
