"""Cross-encoder / LLM-as-judge reranking.

RRF fusion is a cheap first pass that only ever sees *rank position* — it
can't tell "shares keywords with the query" from "actually answers it". A
reranker takes the fused candidate pool and scores each candidate directly
against the query text, trading one extra pass for materially better
precision at the final top_k. `HybridRetriever` fuses down to
`rerank_candidate_pool` (default 20) instead of straight to `top_k` when a
reranker is configured, then the reranker cuts that pool to the requested
`top_k`.

Two backends, one interface:
- CrossEncoderReranker: a small local cross-encoder model. Needs
  sentence-transformers — the same optional dependency as
  EMBEDDING_PROVIDER=local — no API key.
- LLMJudgeReranker: a *single* batched call to the already-configured LLM
  scoring every candidate at once, not one call per candidate — an N-times-
  slower LLM judge would make the cost/latency trade against a cross-encoder
  meaningless before it even starts.

Disabled by default (RERANKER_PROVIDER=none): whichever backend you pick is
a real added cost or added dependency, so it's opt-in rather than forced on
every request.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

from rag_api.adapters.llm.llm_client import LLMClient
from rag_api.domain.models import RetrievedChunk


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        """Return the top_k candidates reordered by relevance to `query`,
        each with `.rerank_score` set."""


class CrossEncoderReranker(Reranker):
    def __init__(self, model_name: str = "ms-marco-MiniLM-L-12-v2"):
        try:
            from flashrank import Ranker
        except ImportError as exc:  # pragma: no cover - exercised via mocked test instead
            raise ImportError(
                "RERANKER_PROVIDER=cross_encoder requires flashrank. "
                "Install with: pip install flashrank"
            ) from exc
            
        # FlashRank has a specific whitelist of model names (e.g., ms-marco-MiniLM-L-12-v2).
        # We safely default to it or use the requested one.
        # Note: If the user provides an HF model name not natively bundled in flashrank's map 
        # (like 'BAAI/bge-reranker-v2-m3' in flashrank 0.2.10), we fallback to the highest 
        # supported flashrank equivalent so it doesn't instantly crash on load.
        from flashrank import Config
        if model_name not in Config.model_file_map:
            import logging
            logging.getLogger(__name__).warning(
                f"Model '{model_name}' is not in flashrank's default map. "
                "Falling back to 'ms-marco-MiniLM-L-12-v2'."
            )
            model_name = "ms-marco-MiniLM-L-12-v2"
            
        self._ranker = Ranker(model_name=model_name)

    def rerank(self, query: str, candidates: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        if not candidates:
            return []
            
        from flashrank import RerankRequest
        
        # Prepare passages for flashrank
        passages = [
            {"id": str(i), "text": c.text, "meta": c.metadata} 
            for i, c in enumerate(candidates)
        ]
        
        req = RerankRequest(query=query, passages=passages)
        results = self._ranker.rerank(req)
        
        # Map the scored results back to our chunk objects
        chunk_map = {str(i): c for i, c in enumerate(candidates)}
        ranked_chunks = []
        for r in results:
            chunk = chunk_map[r["id"]]
            chunk.rerank_score = r["score"]
            ranked_chunks.append(chunk)
            
        return ranked_chunks[:top_k]


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class LLMJudgeReranker(Reranker):
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def rerank(self, query: str, candidates: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        if not candidates:
            return []

        excerpts = "\n\n".join(f"[{i}] {c.text}" for i, c in enumerate(candidates, start=1))
        system = (
            "You score how relevant each numbered excerpt is to a question, on a 0-10 scale "
            "(10 = directly answers it, 0 = irrelevant). Respond with ONLY a JSON object mapping "
            'each excerpt number, as a string, to its score -- e.g. {"1": 8, "2": 2}. No other text.'
        )
        user = f"Question: {query}\n\nExcerpts:\n\n{excerpts}"
        raw = self.llm_client.generate(system, user)

        scores = self._parse_scores(raw, len(candidates))
        for chunk, score in zip(candidates, scores):
            # map [0, 10] to [0, 1]
            chunk.rerank_score = score / 10.0
        ranked = sorted(candidates, key=lambda c: c.rerank_score, reverse=True)
        return ranked[:top_k]

    @staticmethod
    def _parse_scores(raw: str, n: int) -> list[float]:
        """Defensive parsing: a response the model didn't format as asked
        degrades to score 0.0 for whichever candidates couldn't be read —
        which, since Python's sort is stable, falls back to the original
        fusion order rather than raising and losing the request."""
        scores = [0.0] * n
        match = _JSON_OBJECT_RE.search(raw)
        if not match:
            return scores
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return scores
        if not isinstance(parsed, dict):
            return scores
        for key, value in parsed.items():
            try:
                idx = int(key) - 1
                if 0 <= idx < n:
                    scores[idx] = float(value)
            except (TypeError, ValueError):
                continue
        return scores


def build_reranker(
    provider: str,
    *,
    model_name: str | None = None,
    llm_client: LLMClient | None = None,
) -> Reranker | None:
    if provider == "none":
        return None
    if provider == "cross_encoder":
        return CrossEncoderReranker(model_name=model_name or "BAAI/bge-reranker-v2-m3")
    if provider == "llm_judge":
        if llm_client is None:
            raise ValueError(
                "RERANKER_PROVIDER=llm_judge requires an LLM client "
                "(set LLM_PROVIDER to 'anthropic' or 'openai', not 'none')"
            )
        return LLMJudgeReranker(llm_client)
    raise ValueError(f"Unknown reranker provider: {provider!r} (expected 'none', 'cross_encoder' or 'llm_judge')")
