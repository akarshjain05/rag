"""LLM client abstraction — Anthropic, OpenAI, or none.

Lives in its own module (rather than inside generation.py, where it
originated) because `app.reranker` and `app.verification` both also need
`LLMClient` for their own LLM-as-judge calls; importing it from
`app.generation` would make `generation.py` depend on modules that need to
import back from it (`verification.CitationVerifier` is used by
`AnswerGenerator`), which is a cycle. This module has no dependencies on any
of the others, so everything can depend on it instead of on each other.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate(self, system: str, user: str | list[dict]) -> str: ...


class AnthropicLLMClient(LLMClient):
    def __init__(self, model: str = "claude-sonnet-4-5", api_key: str | None = None, max_tokens: int = 1024):
        from anthropic import Anthropic  # local import: optional dependency

        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for LLM_PROVIDER=anthropic")
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, system: str, user: str | list[dict]) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")


class OpenAILLMClient(LLMClient):
    def __init__(self, model: str = "gpt-4o", api_key: str | None = None, base_url: str | None = None, max_tokens: int = 1024):
        from openai import OpenAI  # local import: optional dependency

        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for LLM_PROVIDER=openai")
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, system: str, user: str | list[dict]) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""


def build_llm_client(provider: str, **kwargs) -> LLMClient | None:
    if provider == "anthropic":
        return AnthropicLLMClient(**kwargs)
    if provider == "openai":
        return OpenAILLMClient(**kwargs)
    if provider == "none":
        return None
    raise ValueError(f"Unknown llm provider: {provider!r} (expected 'anthropic', 'openai' or 'none')")
