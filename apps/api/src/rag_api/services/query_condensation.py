import time
from rag_api.core.observability import tracer, llm_calls_total, llm_call_seconds
from rag_api.core.logging import log
from rag_api.adapters.llm.llm_client import LLMClient
from rag_api.services.conversation import Turn


def normalize_query(query: str, llm_client: LLMClient) -> str:
    """Step 1, proactive: fix spelling/typing errors and expand obvious
    acronyms/shorthand -- nothing else. Runs unconditionally, before
    condensation, HyDE, and retrieval -- a typo corrupts dense embeddings,
    BM25 tokens, and (most severely) a cross-encoder reranker's token-level
    comparison identically, so cleaning it up once, up front, fixes all
    three rather than papering over the symptom downstream of each.

    Deliberately narrow in scope: no synonym expansion, no broadening the
    topic, no adding technical terms not implied by the original query --
    that's `expand_query`'s job, reserved for a clean query that still comes
    back low-confidence (a genuine knowledge/vocabulary gap, not a garbled
    one)."""
    system = (
        "You clean up a user's search query before it is used to search a "
        "document index. Fix any spelling or typing errors, and expand "
        "obvious acronyms or shorthand into their full form. Do not add "
        "synonyms, do not broaden the topic, and do not add words that "
        "aren't implied by the original query -- only correct it. If the "
        "query is already clean, return it exactly as-is, unchanged. "
        "Return ONLY the corrected query string, nothing else."
    )
    start = time.perf_counter()
    with tracer.start_as_current_span("normalization.llm_call"):
        corrected_query = llm_client.generate(system, query)
    llm_calls_total.labels(stage="normalize", provider=llm_client.provider_name).inc()
    llm_call_seconds.labels(stage="normalize").observe(time.perf_counter() - start)
    print(f"\n=== NORMALIZED QUERY ===\nOriginal: {query}\nNormalized: {corrected_query}\n")

    return corrected_query.strip()


def condense_query(query: str, history: list[Turn], llm_client: LLMClient) -> str:
    if not history:
        return query

    system = (
        "Given the following conversation history and the user's latest follow-up question, "
        "rewrite the follow-up question to be a standalone query that can be understood "
        "without the conversation history. Do not answer the question, just rewrite it. "
        "If it is already standalone, return it exactly as is."
    )

    llm_history = []
    for turn in history:
        llm_history.append({"role": "user", "content": turn.user})
        llm_history.append({"role": "assistant", "content": turn.assistant})

    start = time.perf_counter()
    with tracer.start_as_current_span("condensation.llm_call"):
        standalone_query = llm_client.generate(system, query, history=llm_history)
    llm_calls_total.labels(stage="condense", provider=llm_client.provider_name).inc()
    llm_call_seconds.labels(stage="condense").observe(time.perf_counter() - start)
    print(f"\n=== CONDENSED QUERY ===\n{standalone_query}\n")

    return standalone_query.strip()


def should_expand_query(max_rerank_score: float, ceiling: float = 0.80) -> bool:
    """Whether CRAG should attempt a query-expansion retry, given the top
    rerank score seen so far. Only a comfortably high score skips expansion
    outright -- everything below `ceiling`, including a near-zero score, is
    now worth one rewrite attempt.

    This used to also require score >= 0.40 (a "very low" score was assumed
    hopeless and not worth expanding). That assumption doesn't hold once
    `normalize_query` already runs upstream of every retrieval: a low score
    on an already-clean query is far more likely to mean genuinely novel or
    underspecified terminology than total irrelevance -- exactly what
    expansion is for. A truly hopeless query still just costs one wasted
    rewrite attempt: the caller only swaps to the expanded chunks if they
    demonstrably score higher, so widening this can't make an answer worse,
    only occasionally slower."""
    return max_rerank_score < ceiling


def expand_query(query: str, llm_client: LLMClient) -> str:
    """Step 3, reactive (CRAG): the query has already been spell-checked by
    `normalize_query` before this is ever called, so this assumes correct
    spelling and focuses entirely on recall -- synonyms, expanded acronyms,
    and related technical terminology the documentation might use that the
    user's own phrasing didn't. Not responsible for fixing typos; one
    reaching here is a normalization gap to fix upstream, not something
    this prompt should compensate for."""
    system = (
        "You are an expert search query expander for a technical RAG system. "
        "The query has already been spell-checked and cleaned up, so assume "
        "it is spelled and phrased correctly -- do not attempt to correct "
        "spelling. It returned low-confidence results anyway, which usually "
        "means it's genuinely underspecified or uses different terminology "
        "than the documentation. Rewrite the query to include synonyms, "
        "expanded acronyms, and related technical terms that might appear "
        "in formal documentation, to improve search recall. "
        "Return ONLY the rewritten query string, nothing else."
    )
    start = time.perf_counter()
    with tracer.start_as_current_span("crag_expansion.llm_call"):
        expanded_query = llm_client.generate(system, query)
    llm_calls_total.labels(stage="expand", provider=llm_client.provider_name).inc()
    llm_call_seconds.labels(stage="expand").observe(time.perf_counter() - start)
    print(f"\n=== CRAG EXPANDED QUERY ===\nOriginal: {query}\nExpanded: {expanded_query}\n")
    return expanded_query.strip()


def generate_hyde(query: str, llm_client: LLMClient) -> str:
    system = (
        "You are an expert technical writer. The user is asking a question that will be used to search a vector database. "
        "Your task is to write a hypothetical passage that perfectly answers the user's question. "
        "Write it exactly as it might appear in a formal textbook, documentation, or technical paper. "
        "Do not include conversational filler like 'Here is a hypothetical document'. "
        "Just output the hypothetical paragraph directly."
    )
    start = time.perf_counter()
    with tracer.start_as_current_span("hyde.llm_call"):
        hyde_doc = llm_client.generate(system, query)
    llm_calls_total.labels(stage="hyde", provider=llm_client.provider_name).inc()
    llm_call_seconds.labels(stage="hyde").observe(time.perf_counter() - start)
    print(f"\n=== HyDE DOCUMENT ===\n{hyde_doc}\n")
    return hyde_doc.strip()
