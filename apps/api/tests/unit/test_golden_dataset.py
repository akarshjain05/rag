from __future__ import annotations

import json

from eval.golden_dataset import NOT_IN_CORPUS, GoldenExample, load_golden_dataset


def test_is_unanswerable_true_for_not_in_corpus_marker():
    example = GoldenExample(id="x", question="q", golden_answer=NOT_IN_CORPUS, category="unanswerable")
    assert example.is_unanswerable is True


def test_is_unanswerable_false_for_a_real_answer():
    example = GoldenExample(id="x", question="q", golden_answer="18 days per year.", category="lookup")
    assert example.is_unanswerable is False


def test_load_golden_dataset_from_file(tmp_path):
    path = tmp_path / "qa.json"
    path.write_text(json.dumps([
        {"id": "q1", "question": "How many days?", "golden_answer": "10.", "category": "lookup",
         "expected_source_documents": ["a.md"], "notes": ""},
    ]))

    examples = load_golden_dataset(path)

    assert len(examples) == 1
    assert examples[0].id == "q1"
    assert examples[0].expected_source_documents == ["a.md"]


def test_bundled_golden_dataset_loads_and_has_at_least_50_examples():
    from pathlib import Path
    bundled_path = Path(__file__).parent.parent.parent.parent.parent / "eval" / "golden_qa.json"
    examples = load_golden_dataset(bundled_path)

    assert len(examples) >= 50
    assert len({e.id for e in examples}) == len(examples), "all ids must be unique"
    assert {e.category for e in examples} == {"lookup", "multi_hop", "unanswerable", "ambiguous"}


def test_bundled_golden_dataset_unanswerable_examples_have_no_expected_sources():
    from pathlib import Path
    bundled_path = Path(__file__).parent.parent.parent.parent.parent / "eval" / "golden_qa.json"
    examples = load_golden_dataset(bundled_path)

    for example in examples:
        if example.category == "unanswerable":
            assert example.is_unanswerable
            assert example.expected_source_documents == []


def test_bundled_golden_dataset_expected_sources_exist_in_golden_corpus():
    from pathlib import Path
    bundled_path = Path(__file__).parent.parent.parent.parent.parent / "eval" / "golden_qa.json"
    corpus_dir = Path(__file__).parent.parent.parent.parent.parent / "eval" / "golden_corpus"
    corpus_files = {p.name for p in corpus_dir.iterdir()}

    examples = load_golden_dataset(bundled_path)
    for example in examples:
        for source in example.expected_source_documents:
            assert source in corpus_files, f"{example.id} references missing corpus file {source}"
