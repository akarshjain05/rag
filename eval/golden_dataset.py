"""Golden Q&A dataset schema and loader for the evaluation framework.

Each example ties a question to specific document(s) in the corpus, a
hand-written reference answer, and a category:

- "lookup": a straightforward single-fact answer in one document.
- "multi_hop": answering correctly requires combining two documents.
- "unanswerable": the corpus genuinely does not contain the answer -- the
  correct system behavior is to say so, not to guess. `golden_answer` is
  the literal string `NOT_IN_CORPUS` for these, handled specially by
  `judges.AnswerCorrectnessJudge`.
- "ambiguous": the question is genuinely underspecified or has more than
  one reasonable reading. `golden_answer` describes the ambiguity itself
  rather than picking one interpretation -- a good system answer should
  surface the ambiguity or pick one reading and answer it clearly, not
  silently assume the only possible reading.

The bundled dataset (`golden_qa.json`, 57 examples) is hand-written against
the bundled `golden_corpus/` (8 fictional company policy documents).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

NOT_IN_CORPUS = "NOT_IN_CORPUS"


@dataclass
class GoldenExample:
    id: str
    question: str
    golden_answer: str
    category: str  # "lookup" | "multi_hop" | "unanswerable" | "ambiguous"
    expected_source_documents: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def is_unanswerable(self) -> bool:
        return self.golden_answer == NOT_IN_CORPUS


def load_golden_dataset(path: str | Path) -> list[GoldenExample]:
    data = json.loads(Path(path).read_text())
    return [GoldenExample(**item) for item in data]
