"""tests/adapters/llm/conftest.py — shared fixtures and test data for LLM adapter tests.

Each adapter constructs httpx.AsyncClient() fresh per call rather than
accepting an injected client, so the standard "pass a client with a
MockTransport" pattern doesn't apply directly. mock_transport instead
monkeypatches httpx.AsyncClient.__init__ for the duration of a test so
any internally-constructed client automatically uses a MockTransport —
no adapter code changes needed, no new dependency, no real network access.

ADAPTER_CASES is the shared behavior-matrix fixture data: one AdapterCase
per real LLM adapter, reused by both test_behavior_matrix.py (uniform
assertions) and test_adapter_specific_behaviors.py (documented per-adapter
divergences — see docs/TESTING.md "Known Gaps").
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from ooagent.adapters.llm.anthropic import AnthropicConfig, AnthropicLLMClient
from ooagent.adapters.llm.gemini import GeminiConfig, GeminiLLMClient
from ooagent.adapters.llm.ollama import OllamaConfig, OllamaLLMClient
from ooagent.adapters.llm.openai import OpenAIConfig, OpenAILLMClient
from ooagent.core.protocols import ILLMClient, LLMVendor

MockHandler = Callable[[httpx.Request], httpx.Response]
MockTransportInstaller = Callable[[MockHandler], None]


@pytest.fixture
def mock_transport(monkeypatch: pytest.MonkeyPatch) -> MockTransportInstaller:
    original_init = httpx.AsyncClient.__init__

    def install(handler: MockHandler) -> None:
        def patched_init(self: httpx.AsyncClient, *args: Any, **kwargs: Any) -> None:
            kwargs.setdefault("transport", httpx.MockTransport(handler))
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    return install


def anthropic_success_body(text: str = "hello") -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 5, "output_tokens": 3},
    }


def openai_success_body(text: str = "hello") -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }


def gemini_success_body(text: str = "hello") -> dict[str, Any]:
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 3},
    }


def ollama_success_body(text: str = "hello") -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }


@dataclass(frozen=True)
class AdapterCase:
    name: str
    vendor: LLMVendor
    make_client: Callable[[], ILLMClient]
    make_client_with_max_tokens: Callable[[int], ILLMClient]
    success_body: dict[str, Any]


ADAPTER_CASES: list[AdapterCase] = [
    AdapterCase(
        name="anthropic",
        vendor="anthropic",
        make_client=lambda: AnthropicLLMClient(AnthropicConfig(api_key="key")),
        make_client_with_max_tokens=lambda mt: AnthropicLLMClient(
            AnthropicConfig(api_key="key", max_tokens=mt)
        ),
        success_body=anthropic_success_body("hello"),
    ),
    AdapterCase(
        name="openai",
        vendor="openai",
        make_client=lambda: OpenAILLMClient(OpenAIConfig(api_key="key")),
        make_client_with_max_tokens=lambda mt: OpenAILLMClient(
            OpenAIConfig(api_key="key", max_tokens=mt)
        ),
        success_body=openai_success_body("hello"),
    ),
    AdapterCase(
        name="gemini",
        vendor="gemini",
        make_client=lambda: GeminiLLMClient(GeminiConfig(api_key="key")),
        make_client_with_max_tokens=lambda mt: GeminiLLMClient(
            GeminiConfig(api_key="key", max_tokens=mt)
        ),
        success_body=gemini_success_body("hello"),
    ),
    AdapterCase(
        name="ollama",
        vendor="ollama",
        make_client=lambda: OllamaLLMClient(OllamaConfig()),
        make_client_with_max_tokens=lambda mt: OllamaLLMClient(OllamaConfig(max_tokens=mt)),
        success_body=ollama_success_body("hello"),
    ),
]

ADAPTER_CASE_IDS: list[str] = [c.name for c in ADAPTER_CASES]
