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
from rag_api.core.logging import log

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def generate(self, system: str | list[dict], user: str | list[dict], history: list[dict] | None = None) -> str: ...
    
    def generate_with_metrics(self, system: str | list[dict], user: str | list[dict], history: list[dict] | None = None) -> tuple[str, dict]:
        import time
        start = time.time()
        ans = self.generate(system, user, history)
        latency = time.time() - start
        return ans, {"ttft": latency, "total_latency": latency, "cost": 0.0}

    @abstractmethod
    def build_image_content(self, image_url: str) -> dict: ...

    def describe_image(self, image_bytes: bytes, media_type: str, prompt: str) -> str: ...


class AnthropicLLMClient(LLMClient):
    @property
    def provider_name(self) -> str:
        return 'anthropic'

    def __init__(self, model: str = "claude-sonnet-4-5", api_key: str | None = None, max_tokens: int = 1024, timeout: float = 120.0):
        from anthropic import Anthropic  # local import: optional dependency

        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for LLM_PROVIDER=anthropic")
        self._client = Anthropic(api_key=api_key, timeout=timeout)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, system: str | list[dict], user: str | list[dict], history: list[dict] | None = None) -> str:
        import anthropic
        messages = list(history) if history else []
        messages.append({"role": "user", "content": user})
        
        while True:
            try:
                resp = self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=system,
                    messages=messages,
                )
                return "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
            except anthropic.BadRequestError as e:
                err_msg = str(e).lower()
                if "too long" in err_msg or "context length" in err_msg or "exceed" in err_msg:
                    # Try to drop the oldest turn (which might be two messages if it's a history turn)
                    if len(messages) > 1:
                        messages.pop(0)
                        if messages and messages[0].get("role") == "assistant":
                            messages.pop(0)
                        continue
                raise e

    def generate_with_metrics(self, system: str | list[dict], user: str | list[dict], history: list[dict] | None = None) -> tuple[str, dict]:
        import anthropic
        import time
        messages = list(history) if history else []
        messages.append({"role": "user", "content": user})
        
        while True:
            try:
                start = time.time()
                resp = self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=system,
                    messages=messages,
                )
                total_latency = time.time() - start
                ans = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
                cost = 0.0
                if hasattr(resp, "usage") and resp.usage:
                    if "sonnet" in self._model.lower():
                        cost = (resp.usage.input_tokens * 3.0 + resp.usage.output_tokens * 15.0) / 1_000_000.0
                    elif "haiku" in self._model.lower():
                        cost = (resp.usage.input_tokens * 0.25 + resp.usage.output_tokens * 1.25) / 1_000_000.0
                    elif "opus" in self._model.lower():
                        cost = (resp.usage.input_tokens * 15.0 + resp.usage.output_tokens * 75.0) / 1_000_000.0
                    else:
                        cost = (resp.usage.input_tokens * 3.0 + resp.usage.output_tokens * 15.0) / 1_000_000.0
                return ans, {"ttft": total_latency, "total_latency": total_latency, "cost": cost}
            except anthropic.BadRequestError as e:
                err_msg = str(e).lower()
                if "too long" in err_msg or "context length" in err_msg or "exceed" in err_msg:
                    if len(messages) > 1:
                        messages.pop(0)
                        if messages and messages[0].get("role") == "assistant":
                            messages.pop(0)
                        continue
                raise e

    def generate_with_metrics(self, system: str | list[dict], user: str | list[dict], history: list[dict] | None = None) -> tuple[str, dict]:
        import anthropic
        import time
        messages = list(history) if history else []
        messages.append({"role": "user", "content": user})
        
        while True:
            try:
                start = time.time()
                resp = self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=system,
                    messages=messages,
                )
                total_latency = time.time() - start
                ans = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
                cost = 0.0
                if hasattr(resp, "usage") and resp.usage:
                    if "sonnet" in self._model.lower():
                        cost = (resp.usage.input_tokens * 3.0 + resp.usage.output_tokens * 15.0) / 1_000_000.0
                    elif "haiku" in self._model.lower():
                        cost = (resp.usage.input_tokens * 0.25 + resp.usage.output_tokens * 1.25) / 1_000_000.0
                    elif "opus" in self._model.lower():
                        cost = (resp.usage.input_tokens * 15.0 + resp.usage.output_tokens * 75.0) / 1_000_000.0
                    else:
                        cost = (resp.usage.input_tokens * 3.0 + resp.usage.output_tokens * 15.0) / 1_000_000.0
                return ans, {"ttft": total_latency, "total_latency": total_latency, "cost": cost}
            except anthropic.BadRequestError as e:
                err_msg = str(e).lower()
                if "too long" in err_msg or "context length" in err_msg or "exceed" in err_msg:
                    if len(messages) > 1:
                        messages.pop(0)
                        if messages and messages[0].get("role") == "assistant":
                            messages.pop(0)
                        continue
                raise e

    def build_image_content(self, image_url: str) -> dict:
        import urllib.request
        import base64
        import mimetypes
        try:
            req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                image_bytes = response.read()
                content_type = response.headers.get_content_type()
        except Exception:
            image_bytes = b""
            content_type = "image/jpeg"
        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "type": "image", 
            "source": {
                "type": "base64", 
                "media_type": content_type, 
                "data": b64_data
            }
        }

    def describe_image(self, image_bytes: bytes, media_type: str, prompt: str) -> str:
        import base64
        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_data,
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }]
        )
        return "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")


class OpenAILLMClient(LLMClient):
    @property
    def provider_name(self) -> str:
        return 'openai'

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None, base_url: str | None = None, max_tokens: int = 1024, timeout: float = 120.0):
        from openai import OpenAI  # local import: optional dependency

        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for LLM_PROVIDER=openai")
        # Fail fast: if the upstream API (like NVIDIA NIM) goes down and returns 500s,
        # we do not want to silently hang for 5 minutes retrying dead endpoints.
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=2)
        self._model = model
        
        if "kimi-k3" in self._model:
            max_tokens = 16384
            
        self._max_tokens = max_tokens

    def generate(self, system: str | list[dict], user: str | list[dict], history: list[dict] | None = None) -> str:
        import openai
        if isinstance(system, list):
            system_str = "".join([block.get("text", "") for block in system])
            messages = [{"role": "system", "content": system_str}]
        else:
            messages = [{"role": "system", "content": system}]
            
        history_msgs = list(history) if history else []
        
        while True:
            current_messages = messages + history_msgs + [{"role": "user", "content": user}]
            try:
                kwargs = {
                    "model": self._model,
                    "max_tokens": self._max_tokens,
                    "messages": current_messages,
                }
                
                # Apply specific parameters requested for moonshotai/kimi-k3
                if "kimi-k3" in self._model:
                    kwargs["temperature"] = 1
                    kwargs["seed"] = 0
                    kwargs["extra_body"] = {"reasoning_effort": "max"}
                    
                resp = self._client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content or ""
            except openai.BadRequestError as e:
                # Handle OpenAI context_length_exceeded
                if e.code == 'context_length_exceeded' or 'context_length_exceeded' in str(e) or 'maximum context length' in str(e):
                    if len(history_msgs) > 0:
                        history_msgs.pop(0)
                        if history_msgs and history_msgs[0].get("role") == "assistant":
                            history_msgs.pop(0)
                        continue
                raise e

    def generate_with_metrics(self, system: str | list[dict], user: str | list[dict], history: list[dict] | None = None) -> tuple[str, dict]:
        import openai
        import time
        if isinstance(system, list):
            system_str = "".join([block.get("text", "") for block in system])
            messages = [{"role": "system", "content": system_str}]
        else:
            messages = [{"role": "system", "content": system}]
            
        history_msgs = list(history) if history else []
        
        while True:
            current_messages = messages + history_msgs + [{"role": "user", "content": user}]
            try:
                kwargs = {
                    "model": self._model,
                    "max_tokens": self._max_tokens,
                    "messages": current_messages,
                    "stream": True,
                    "stream_options": {"include_usage": True}
                }
                
                if "kimi-k3" in self._model:
                    kwargs["temperature"] = 1
                    kwargs["seed"] = 0
                    kwargs["extra_body"] = {"reasoning_effort": "max"}
                    
                start_time = time.time()
                ttft = None
                ans_chunks = []
                usage = None
                
                resp = self._client.chat.completions.create(**kwargs)
                for chunk in resp:
                    if ttft is None:
                        ttft = time.time() - start_time
                    if getattr(chunk.choices, '__len__', lambda: 0)() > 0 and getattr(chunk.choices[0].delta, 'content', None):
                        ans_chunks.append(chunk.choices[0].delta.content)
                    if hasattr(chunk, "usage") and chunk.usage:
                        usage = chunk.usage
                        
                total_latency = time.time() - start_time
                ans = "".join(ans_chunks)
                cost = 0.0
                if usage:
                    cost = (usage.prompt_tokens * 0.005 + usage.completion_tokens * 0.015) / 1000.0
                    
                return ans, {"ttft": ttft or total_latency, "total_latency": total_latency, "cost": cost}
            except openai.BadRequestError as e:
                if e.code == 'context_length_exceeded' or 'context_length_exceeded' in str(e) or 'maximum context length' in str(e):
                    if len(history_msgs) > 0:
                        history_msgs.pop(0)
                        if history_msgs and history_msgs[0].get("role") == "assistant":
                            history_msgs.pop(0)
                        continue
                raise e

    def build_image_content(self, image_url: str) -> dict:
        return {"type": "image_url", "image_url": {"url": image_url}}

    def describe_image(self, image_bytes: bytes, media_type: str, prompt: str) -> str:
        import base64
        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{b64_data}"
                        }
                    }
                ]
            }]
        )
        return resp.choices[0].message.content or ""


def build_llm_client(provider: str, **kwargs) -> LLMClient | None:
    if provider == "anthropic":
        kwargs.pop('base_url', None)
        return AnthropicLLMClient(**kwargs)
    if provider == "openai":
        return OpenAILLMClient(**kwargs)
    if provider == "none":
        return None
    raise ValueError(f"Unknown llm provider: {provider!r} (expected 'anthropic', 'openai' or 'none')")
