import re
with open("docs/architecture.md", "r") as f:
    text = f.read()

text = text.replace(
""" [CRAG loop]          if top rerank score is "ambiguous" (0.40–0.79),
                      expand the query with an LLM and re-retrieve once""",
""" [Semantic Cache]    checks for 95%+ cosine similarity in Qdrant; if hit,
                      returns cached payload immediately (bypassing all else)
        │
        ▼
 [normalizer]        proactively fixes typos and acronyms using a cheap
                      Tier 3 model to prevent token destruction
        │
        ▼
 [CRAG loop]          if top rerank score is < 0.80, expand the
                      query with domain synonyms and re-retrieve once"""
)

text = text.replace(
"""3. **CRAG expansion loop** — after the first retrieval, if a reranker is
   configured and the top rerank score falls in `[0.40, 0.80)`
   ("ambiguous"), the query is expanded with LLM-generated synonyms/
   acronyms and retrieval is re-run once; the expanded result is kept
   only if its top score actually improved. These thresholds are
   currently hardcoded in `ask.py`, not settings-driven.""",
"""3. **Semantic Caching** — instantly returns previously generated answers
   if the exact intent (Cosine Similarity > 0.95) was recently asked,
   enforcing a configurable TTL expiration.
4. **Proactive Normalization** — unconditionally intercepts every query
   before retrieval and routes it to `NORMALIZER_MODEL` (e.g. Haiku) to
   fix spelling and syntax, neutralizing Cross-Encoder brittleness.
5. **CRAG expansion loop** — after the first retrieval, if a reranker is
   configured and the top rerank score is `< 0.80`, the query is expanded
   with LLM-generated synonyms/architectural terms and retrieval is re-run.
   The expanded result is kept only if its top score actually improved."""
)

with open("docs/architecture.md", "w") as f:
    f.write(text)
