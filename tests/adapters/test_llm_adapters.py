"""tests/adapters/test_llm_adapters.py — LLM vendor adapters + CachingLLMProxy.

Uses httpx.MockTransport to intercept requests deterministically — no real
network calls. Each adapter opens its own httpx.AsyncClient per call, so the
mock transport is injected by monkeypatching httpx.AsyncClient's default
transport is not directly supported; instead we verify request-building and
response-parsing directly against the private _build_body/_parse methods,
which is what the adapters' own translation verified against the TS source.
"""

from __future__ import annotations

import pytest

from ooagent.adapters.llm.anthropic import AnthropicConfig, AnthropicLLMClient
from ooagent.adapters.llm.caching_proxy import CachingLLMProxy
from ooagent.adapters.llm.gemini import GeminiConfig, GeminiLLMClient
from ooagent.adapters.llm.ollama import OllamaConfig, OllamaLLMClient
from ooagent.adapters.llm.openai import OpenAIConfig, OpenAILLMClient
from ooagent.core.protocols import (
    CompletionRequest,
    CompletionResponse,
    Message,
    TokenLimitError,
    TokenUsage,
)


def test_anthropic_client_exposes_vendor_and_defaults() -> None:
    client = AnthropicLLMClient(AnthropicConfig(api_key="key"))
    assert client.vendor == "anthropic"
    assert client.supports_tools is True
    assert client.max_tokens == 8192


def test_openai_client_build_body_includes_tools_and_tool_choice() -> None:
    client = OpenAILLMClient(OpenAIConfig(api_key="key"))
    request = CompletionRequest(
        messages=[Message(role="user", content="hi")],
        tools=[{"type": "function", "function": {"name": "echo"}}],
    )
    body = client._build_body(request)
    assert body["tool_choice"] == "auto"
    assert body["tools"] == request.tools


def test_gemini_client_build_body_separates_system_instruction() -> None:
    client = GeminiLLMClient(GeminiConfig(api_key="key"))
    request = CompletionRequest(
        messages=[
            Message(role="system", content="be terse"),
            Message(role="user", content="hi"),
        ]
    )
    body = client._build_body(request)
    assert body["systemInstruction"]["parts"][0]["text"] == "be terse"
    assert len(body["contents"]) == 1


def test_ollama_client_does_not_support_tools() -> None:
    client = OllamaLLMClient(OllamaConfig())
    assert client.supports_tools is False
    assert client.vendor == "ollama"


async def test_anthropic_complete_raises_token_limit_error_when_oversized() -> None:
    client = AnthropicLLMClient(AnthropicConfig(api_key="key", max_tokens=1))
    request = CompletionRequest(messages=[Message(role="user", content="x" * 100)])
    with pytest.raises(TokenLimitError):
        await client.complete(request)


async def test_caching_proxy_caches_deterministic_completions() -> None:
    call_count = 0

    class _CountingClient:
        vendor = "anthropic"
        model_id = "stub"
        max_tokens = 4096
        supports_tools = False

        async def complete(self, request: CompletionRequest) -> CompletionResponse:
            nonlocal call_count
            call_count += 1
            return CompletionResponse(
                content="cached",
                stop_reason="end_turn",
                usage=TokenUsage(input_tokens=1, output_tokens=1),
            )

        async def stream(self, request):
            yield  # pragma: no cover - not exercised in this test

    proxy = CachingLLMProxy(_CountingClient())
    request = CompletionRequest(messages=[Message(role="user", content="hi")], temperature=0)
    await proxy.complete(request)
    await proxy.complete(request)
    assert call_count == 1
    assert proxy.cache_size == 1
