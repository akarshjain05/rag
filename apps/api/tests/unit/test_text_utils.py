from __future__ import annotations

from rag_api.domain.chunking.text_utils import split_sentences


def test_splits_on_sentence_terminators():
    assert split_sentences("First sentence. Second sentence. Third one!") == [
        "First sentence.",
        "Second sentence.",
        "Third one!",
    ]


def test_treats_paragraph_breaks_as_boundaries():
    result = split_sentences("Paragraph one has no period\n\nParagraph two here.")
    assert result == ["Paragraph one has no period", "Paragraph two here."]


def test_strips_leading_markdown_heading_marker():
    result = split_sentences("## Vacation Policy\n\nEmployees accrue days monthly.")
    assert result == ["Vacation Policy", "Employees accrue days monthly."]


def test_empty_text_returns_empty_list():
    assert split_sentences("") == []
    assert split_sentences("   \n\n  ") == []


def test_collapses_internal_whitespace():
    result = split_sentences("This   has\nextra   whitespace.")
    assert result == ["This has extra whitespace."]
