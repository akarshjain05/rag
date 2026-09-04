from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rag_api.adapters.llm.llm_client import AnthropicLLMClient, OpenAILLMClient, build_llm_client


def test_anthropic_client_requires_api_key():
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        AnthropicLLMClient(api_key=None)


def test_anthropic_client_calls_sdk_correctly(monkeypatch):
    text_block = MagicMock(type="text", text="Hello from Claude [1].")
    fake_response = MagicMock(content=[text_block])
    fake_instance = MagicMock()
    fake_instance.messages.create.return_value = fake_response
    monkeypatch.setattr("anthropic.Anthropic", lambda api_key, base_url=None, timeout=None: fake_instance)

    client = AnthropicLLMClient(model="claude-sonnet-4-5", api_key="sk-ant-test")
    result = client.generate("system prompt", "user prompt")

    assert result == "Hello from Claude [1]."
    fake_instance.messages.create.assert_called_once_with(
        model="claude-sonnet-4-5", max_tokens=1024, system="system prompt", messages=[{"role": "user", "content": "user prompt"}]
    )


def test_openai_llm_client_requires_api_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAILLMClient(api_key=None)


def test_openai_llm_client_calls_sdk_correctly(monkeypatch):
    fake_message = MagicMock(content="Hello from GPT [1].")
    fake_choice = MagicMock(message=fake_message)
    fake_response = MagicMock(choices=[fake_choice])
    fake_instance = MagicMock()
    fake_instance.chat.completions.create.return_value = fake_response
    monkeypatch.setattr("openai.OpenAI", lambda api_key, base_url=None, timeout=None: fake_instance)

    client = OpenAILLMClient(model="gpt-4o", api_key="sk-test")
    result = client.generate("system prompt", "user prompt")

    assert result == "Hello from GPT [1]."


def test_build_llm_client_none_provider_returns_none():
    assert build_llm_client("none") is None


def test_build_llm_client_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown llm provider"):
        build_llm_client("not-a-real-provider")
