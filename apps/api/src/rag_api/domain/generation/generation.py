"""Answer generation over retrieved chunks: grounded prompt, citations, and
answer confidence.

Every retrieved chunk becomes a numbered context excerpt ([1], [2], ...) and
the LLM is instructed to answer only from them, citing every claim. Two
independent citation checks run on top of that, deliberately kept separate
because they catch different failure modes:

- `_extract_and_validate_citations` (structural): does citation marker [N]
  even refer to a real excerpt? Catches a hallucinated citation *number*.
- `app.verification.CitationVerifier` (semantic, optional, needs an LLM):
  does the excerpt [N] actually *support* the specific claim it's attached
  to? This is the "quality layer most RAG systems skip entirely" -- an
  in-range citation can still be wrong.

`AnswerGenerator.generate()` also computes a composite confidence score
(retrieval confidence + citation coverage + completeness -- see
`app.confidence`) and, when retrieval confidence falls below
`low_confidence_threshold`, skips generation entirely and returns a
structured "I don't know" response instead of risking a fabricated answer
over a wasted LLM call.

`llm_provider="none"` needs no API key at all: it returns the single
top-ranked chunk verbatim as an extractive "answer", clearly labeled as
such, so the full ingest -> retrieve -> answer loop is demonstrable without
any paid API key. `EMBEDDING_PROVIDER=local` + `LLM_PROVIDER=none` runs the
entire system for free.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rag_api.domain.generation.confidence import (
    compute_citation_coverage,
    compute_composite_confidence,
    compute_retrieval_confidence,
    unsupported_citation_markers,
)
from rag_api.adapters.llm.llm_client import LLMClient
from rag_api.domain.models import RetrievedChunk
from rag_api.domain.generation.verification import CitationVerifier, split_into_claims

SYSTEM_PROMPT = """You are a precise assistant answering questions using ONLY the provided \
numbered context excerpts from internal company documentation.

Rules:
- Answer using only information present in the context excerpts below.
- Every factual claim must be followed by a citation marker, e.g. [1] or [2][3], \
referencing the excerpt(s) it came from.
- Never invent a citation number that is not listed below.
- If the excerpts don't contain enough information to answer, say so plainly \
instead of guessing."""

_CITATION_RE = re.compile(r"\[(\d+)\]")


# --------------------------------------------------------------------------
# Answer generation + citation building/validation
# --------------------------------------------------------------------------
@dataclass
class GenerationResult:
    answer: str
    sources: list[dict] = field(default_factory=list)
    used_citation_markers: list[int] = field(default_factory=list)
    invalid_citation_markers: list[int] = field(default_factory=list)
    mode: str = "llm"  # "llm" | "extractive" | "no_context" | "low_confidence"
    retrieval_confidence: float | None = None
    citation_coverage: float | None = None
    citation_coverage_basis: str | None = None  # "verified" | "structural" | "extractive"
    completeness: float | None = None
    composite_confidence: float | None = None
    unsupported_citation_markers: list[int] = field(default_factory=list)


def _build_context_block(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    # Dynamic Context Pruning: Drop chunks with rerank score < 0.30 to avoid confusing the LLM with noise.
    # The chunks are still preserved in the overall list so the UI can display them (with low scores).
    for i, c in enumerate(chunks, start=1):
        if c.rerank_score is not None and c.rerank_score < 0.30:
            continue
            
        loc = [c.metadata.get("source_document", "unknown")]
        section = c.metadata.get("section_heading")
        if section:
            loc.append(f"section: {section}")
        page = c.metadata.get("page_number", -1)
        if page and page != -1:
            loc.append(f"page {page}")
        blocks.append(f"[{i}] ({', '.join(loc)})\n{c.text}")
    return "\n\n".join(blocks)


def build_sources(chunks: list[RetrievedChunk]) -> list[dict]:
    sources = []
    for i, c in enumerate(chunks, start=1):
        page = c.metadata.get("page_number", -1)
        img_ref = c.metadata.get("image_ref")
        sources.append(
            {
                "marker": i,
                "chunk_id": c.chunk_id,
                "text": c.text,
                "source_document": c.metadata.get("source_document"),
                "section_heading": c.metadata.get("section_heading") or None,
                "page_number": page if page != -1 else None,
                "content_type": c.metadata.get("content_type"),
                "image_url": f"/v1/images/{img_ref}" if img_ref else None,
                "dense_rank": c.dense_rank,
                "sparse_rank": c.sparse_rank,
                "rerank_score": c.rerank_score,
            }
        )
    return sources


def _extract_and_validate_citations(answer: str, num_sources: int) -> tuple[list[int], list[int]]:
    found = sorted({int(m) for m in _CITATION_RE.findall(answer)})
    valid = [m for m in found if 1 <= m <= num_sources]
    invalid = [m for m in found if not (1 <= m <= num_sources)]
    return valid, invalid


def _build_low_confidence_answer(chunks: list[RetrievedChunk], retrieval_confidence: float, threshold: float) -> str:
    found_docs = sorted({c.metadata.get("source_document", "unknown") for c in chunks})
    where = f"The closest matches were in: {', '.join(found_docs)}." if found_docs else "No indexed content was a reasonable match at all."
    checked = "those documents" if found_docs else "the source documentation"
    return (
        f"I don't have confident enough information in the indexed documents to answer this reliably "
        f"(retrieval confidence {retrieval_confidence:.2f} is below the {threshold:.2f} threshold). "
        f"{where} You may want to check {checked} manually, or rephrase the question."
    )


class AnswerGenerator:
    def __init__(
        self,
        llm_client: LLMClient | None,
        mode: str,
        *,
        citation_verifier: CitationVerifier | None = None,
        low_confidence_threshold: float | None = 0.3,
    ):
        """mode: "llm" (llm_client must be set) or "extractive" (llm_client
        is ignored/None) — pass the resolved mode explicitly rather than
        inferring it from `llm_client is None`, so tests can force the
        extractive path even with a client configured.

        citation_verifier: when set, claim-level support is checked via an
        LLM judge and `citation_coverage` uses the "verified" basis; when
        None, coverage falls back to the "structural" basis (has a citation
        at all) since there's no judge available to say whether it's right.

        low_confidence_threshold: retrieval confidence below this skips
        generation entirely in favor of a structured "I don't know"
        response. Pass None to disable the check.
        """
        self.llm_client = llm_client
        self.mode = mode
        self.citation_verifier = citation_verifier
        self.low_confidence_threshold = low_confidence_threshold

    def generate(self, query: str, chunks: list[RetrievedChunk], image_url: str | None = None, history: list[dict] | None = None, verify_citations: bool | None = None) -> GenerationResult:
        if not chunks:
            return GenerationResult(
                answer="No relevant context was found in the indexed documents for this question.",
                mode="no_context",
                retrieval_confidence=0.0,
                composite_confidence=compute_composite_confidence(0.0, None, None),
            )

        retrieval_confidence = compute_retrieval_confidence(chunks)
        sources = build_sources(chunks)

        if self.low_confidence_threshold is not None and retrieval_confidence < self.low_confidence_threshold:
            return GenerationResult(
                answer=_build_low_confidence_answer(chunks, retrieval_confidence, self.low_confidence_threshold),
                sources=sources,
                mode="low_confidence",
                retrieval_confidence=retrieval_confidence,
                composite_confidence=compute_composite_confidence(retrieval_confidence, None, None),
            )

        if self.mode == "extractive":
            top = chunks[0]
            answer = f"{top.text.strip()} [1]"
            valid, invalid = _extract_and_validate_citations(answer, len(chunks))
            # the whole answer IS chunk [1] verbatim -- trivially fully cited by construction
            composite = compute_composite_confidence(retrieval_confidence, 1.0, None)
            return GenerationResult(
                answer=answer,
                sources=sources,
                used_citation_markers=valid,
                invalid_citation_markers=invalid,
                mode="extractive",
                retrieval_confidence=retrieval_confidence,
                citation_coverage=1.0,
                citation_coverage_basis="extractive",
                composite_confidence=composite,
            )

        # DYNAMIC CONTEXT PRUNING: Only pass chunks that survived the threshold to the LLM to prevent 'Lost in the Middle' hallucinations!
        pruned_chunks = chunks
        if self.low_confidence_threshold is not None:
            pruned_chunks = [c for c in chunks if (c.rerank_score is None) or (c.rerank_score >= self.low_confidence_threshold)]
            
        context_block = _build_context_block(pruned_chunks)
        user_prompt_text = f"Context excerpts:\n\n{context_block}\n\nQuestion: {query}\n\nAnswer:"
        
        if image_url:
            user_prompt = [
                {"type": "text", "text": user_prompt_text},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]
        else:
            user_prompt = user_prompt_text

        print(f"\n=== GENERATOR PROMPT ===\n{user_prompt}\n=== HISTORY ===\n{history}\n")
        raw_answer = self.llm_client.generate(SYSTEM_PROMPT, user_prompt, history=history)  # type: ignore[union-attr]
        valid, invalid = _extract_and_validate_citations(raw_answer, len(chunks))

        unsupported: list[int] = []
        completeness: float | None = None
        
        do_verify = self.citation_verifier is not None
        if verify_citations is not None:
            do_verify = verify_citations and self.citation_verifier is not None

        if do_verify:

            verification = self.citation_verifier.verify(query, raw_answer, chunks)
            unsupported = unsupported_citation_markers(verification.claims)
            completeness = verification.completeness
            coverage, basis = compute_citation_coverage(verification.claims)
        else:
            coverage, basis = compute_citation_coverage(split_into_claims(raw_answer))

        composite = compute_composite_confidence(retrieval_confidence, coverage, completeness)

        return GenerationResult(
            answer=raw_answer,
            sources=sources,
            used_citation_markers=valid,
            invalid_citation_markers=invalid,
            mode="llm",
            retrieval_confidence=retrieval_confidence,
            citation_coverage=coverage,
            citation_coverage_basis=basis,
            completeness=completeness,
            composite_confidence=composite,
            unsupported_citation_markers=unsupported,
        )
