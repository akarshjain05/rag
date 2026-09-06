# Golden Q&A Evaluation Suite

Source: `eval/golden_dataset.py`, `eval/golden_qa.json`,
`eval/golden_corpus/`, `eval/judges.py`, `eval/eval_runner.py`,
`eval/run_eval_suite.py`.

Answers "was the *generated answer* any good?" — a broader question than
the retrieval-only harness (see
[`02-retrieval-eval-harness.md`](./02-retrieval-eval-harness.md)), which
only checks whether the right chunks were found.

## Dataset

57 hand-written examples (`eval/golden_qa.json`) against 8 fictional
company policy documents (`eval/golden_corpus/`), across four categories:

| Category | Count | What it tests |
|---|---|---|
| `lookup` | 24 | a straightforward single-fact answer in one document |
| `multi_hop` | 16 | answering correctly requires combining two documents |
| `unanswerable` | 9 | plausible-sounding but genuinely not covered by the corpus — correct behavior is declining, not fabricating |
| `ambiguous` | 8 | genuinely underspecified or has more than one reasonable reading — correct behavior is surfacing that, not silently picking one facet |

Each example: `{id, question, golden_answer, category,
expected_source_documents, notes}`. `golden_answer` for `unanswerable`
examples is the literal string `NOT_IN_CORPUS`; for `ambiguous` examples
it describes the ambiguity itself rather than picking one reading.

## Running it

```bash
python eval/run_eval_suite.py
python eval/run_eval_suite.py --compare-chunking-strategies
python eval/run_eval_suite.py --dataset my_qa.json --docs-dir my_docs/
```

**Needs a real LLM** (`LLM_PROVIDER=anthropic` or `openai`) — both judge
metrics below require an LLM judge; there is no zero-API-key mode for
this harness (unlike the main pipeline's extractive fallback).

## The two LLM-as-judge metrics

- **`AnswerCorrectnessJudge`** — does the generated answer convey the
  same key information as the golden answer? Category-aware: for
  `unanswerable` examples, correct means the system declined rather than
  fabricated; for `ambiguous` examples, correct means the answer
  surfaces the ambiguity or clearly answers one reasonable reading, not
  that it silently assumed the only possible one.
- **`FaithfulnessJudge`** — is *every* claim in the answer (cited or
  not) grounded in the *full* retrieved context, in one batched call?
  This is broader than the runtime `CitationVerifier`, which only checks
  claims that already carry a citation marker against their specific
  cited excerpt — an uncited, hallucinated claim slipped in alongside
  otherwise-correct cited claims is exactly what citation accuracy alone
  can't see, and what faithfulness catches.

Both judges degrade to `None` (not a crash, not a silent `False`) when
the LLM's response can't be parsed as the expected JSON shape — see
`eval/metrics.py::_mean`, which averages only over cases that produced a
value, so an unparseable judge result doesn't corrupt the aggregate.

## Retrieval relevance and citation accuracy

Computed without an LLM judge, directly from the pipeline's own output:

- **Retrieval relevance** — recall of `expected_source_documents` among
  what was actually retrieved. `None` (not `0.0`) for `unanswerable`
  examples, which have nothing correct to retrieve.
- **Citation accuracy** — read directly off the live pipeline's
  `citation_coverage` (verified basis), not a separate computation — the
  eval suite exercises the same production code path a real query would
  hit.

## Bringing your own dataset

`my_qa.json` is a JSON list matching `GoldenExample`'s fields; point
`--docs-dir` at your own corpus. Do this before trusting any tuning
decision made against the bundled fictional corpus — 57 examples over 8
fictional documents is a template and a starting point, not sufficient
coverage for a production system's own documents.
# Retrieval Evaluation Harness

Source: `eval/run_retrieval_eval.py`.

Answers a narrower question than the golden Q&A suite: "did we find the
right chunks?" — no generation in the loop, so it needs no LLM and is
fast enough to run on every retrieval-affecting change.

## Metrics

For each `{query, expected_source}` pair, checks whether
`expected_source` appears in the top-k results of dense-only,
sparse-only, and hybrid (RRF) retrieval:

- **Recall@k** — fraction of queries where the expected source appeared
  anywhere in the top k results.
- **MRR** (Mean Reciprocal Rank) — rewards the expected source appearing
  *higher* in the ranking, not just present.

Dense and sparse baselines take the top-k of their own ranked list;
hybrid fuses the full retrieval pool down to top-k — matching exactly
how each mode is actually used in `HybridRetriever`, so the comparison
reflects real usage rather than an artificially inflated pool for
hybrid alone.

## Running it

```bash
# Self-contained demo: 4 small bundled policy docs, 5 labeled queries
python eval/run_retrieval_eval.py --sample

# Your own corpus
python eval/run_retrieval_eval.py --dataset queries.json --docs-dir ./my_docs
```

`queries.json` is a JSON list of
`{"query": "...", "expected_source": "filename.md"}` objects —
`expected_source` must exactly match a filename under `--docs-dir`.

## Interpreting a small sample run

The bundled `--sample` corpus is deliberately easy (4 short, topically
distinct documents, 5 unambiguous queries) — every mode should score
recall 1.0 on it. That's a smoke test confirming the harness itself
works, not evidence that hybrid retrieval is worth its complexity on
your real corpus. The harness earns its keep on larger, harder, real
corpora where dense, sparse, and hybrid actually diverge — run it there
before drawing conclusions.

## When to run this vs. the golden Q&A suite

Run this first, and more often — it's cheap (no LLM judge) and answers
the retrieval-quality question in isolation. Only move to the full
golden Q&A suite once retrieval looks solid and you want to know whether
generation, citations, and confidence scoring are also behaving
correctly on top of it.
# Metrics Reference

## Retrieval-eval metrics (`eval/run_retrieval_eval.py`)

| Metric | Formula | Notes |
|---|---|---|
| Recall@k | `hits / n_queries` | a "hit" is `expected_source` appearing anywhere in the top-k results |
| MRR | `mean(1 / rank_of_expected_source)` | `0.0` contribution if not found in the pool at all |

## Golden-suite per-case metrics (`eval/metrics.py`)

| Metric | Source | Range | `None` when |
|---|---|---|---|
| `answer_correct` | `AnswerCorrectnessJudge` | `bool \| None` | judge response unparseable |
| `faithfulness` | `FaithfulnessJudge.grounded_fraction` | `[0,1] \| None` | judge response unparseable; `1.0` vacuously if the answer had zero claims |
| `retrieval_relevance` | `compute_retrieval_relevance` | `[0,1] \| None` | `None` specifically for `unanswerable` examples — no expected documents exist to score recall against |
| `citation_accuracy` | pipeline's own `citation_coverage` | `[0,1] \| None` | read directly from the live `GenerationResult`, not recomputed |

`summarize_results()` averages each metric only over cases that produced
a non-`None` value for it (`_mean`) — a structurally-inapplicable metric
(e.g. retrieval relevance on an unanswerable question) is excluded from
that average rather than either being dropped as a zero or corrupting
the mean for questions where it *is* applicable. Aggregates are reported
both `overall` and `by_category`.

## Runtime confidence metrics (`rag_api/domain/generation/confidence.py`)

These are what a live `/v1/ask` response actually returns, computed
without any offline judge:

| Metric | Formula | Notes |
|---|---|---|
| `retrieval_confidence` | exponentially-decayed weighted average of chunk similarity/rerank scores, sorted descending, weight `0.5^i` | a long tail of weak matches doesn't drag down a strong top hit; a sparse-only hit (no dense signal) contributes `0.0` |
| `citation_coverage` | fraction of claims judged well-cited | basis is `"verified"` when an LLM judge actually checked support, `"structural"` when only "has a citation at all" was checkable, `"extractive"` (trivially `1.0`) in extractive mode |
| `completeness` | LLM-judge 0–1 rating of whether the answer addresses the whole question | only computed when citation verification ran |
| `composite_confidence` | `0.50 * retrieval + 0.30 * coverage + 0.20 * completeness` (missing sub-scores default to neutral values, not zero, before weighting) | a plain weighted mean, explicitly not a calibrated cross-system probability — a consistent ordinal signal for *this* system only |

## Interpreting confidence numbers

`retrieval_confidence` is not comparable across different embedding
models or corpora — it is only meaningful as a relative signal within
one deployment's own history (e.g. "this query scored lower than usual
for this corpus"), not as an absolute quality bar to publish externally.

`citation_coverage_basis` is the field to check first if a response's
coverage number looks unexpectedly low or high — a `"structural"` basis
means no semantic check ran at all (either verification is disabled, or
no LLM is configured), so the number reflects "has a citation" rather
than "the citation is actually right."
