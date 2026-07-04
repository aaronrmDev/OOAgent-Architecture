"""tests/stub_llm_client.py — Deterministic ILLMClient for unit tests."""

from __future__ import annotations

import math
from collections.abc import AsyncIterator
from re import Pattern
from typing import Any

from ooagent.core.protocols import (
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    ILLMClient,
    LLMVendor,
    TokenLimitError,
    TokenUsage,
)


class _ScriptEntry:
    """Scripted response entry keyed by a message-content pattern."""

    __slots__ = ("pattern", "response")

    def __init__(self, pattern: str | Pattern[str], response: dict[str, Any]) -> None:
        self.pattern = pattern
        self.response = response


class StubLLMClient(ILLMClient):
    """Scripted responses keyed by message content pattern — §17 CLAUDE.md."""

    def __init__(
        self,
        vendor: LLMVendor = "anthropic",
        model: str = "stub-1.0",
        max_tokens: int = 4096,
        supports_tools: bool = False,
    ) -> None:
        self._vendor = vendor
        self._model_id = model
        self._max_tokens = max_tokens
        self._supports_tools = supports_tools
        self._scripts: list[_ScriptEntry] = []
        self._call_count = 0

    def add_script(self, pattern: str | Pattern[str], response: dict[str, Any]) -> StubLLMClient:
        """Fluent API for scripting responses."""
        self._scripts.append(_ScriptEntry(pattern, response))
        return self

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def vendor(self) -> LLMVendor:
        return self._vendor

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @property
    def supports_tools(self) -> bool:
        return self._supports_tools

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._call_count += 1
        estimated = math.ceil(sum(len(m.content) for m in request.messages) / 4)
        if estimated > self._max_tokens:
            raise TokenLimitError(estimated, self._max_tokens)

        last_user = ""
        for message in reversed(request.messages):
            if message.role == "user":
                last_user = message.content
                break

        for entry in self._scripts:
            if isinstance(entry.pattern, str):
                matches = entry.pattern in last_user
            else:
                matches = entry.pattern.search(last_user) is not None
            if matches:
                usage = entry.response.get("usage") or {
                    "input_tokens": 10,
                    "output_tokens": 20,
                }
                return CompletionResponse(
                    content=entry.response.get("content", "Stub response."),
                    stop_reason=entry.response.get("stop_reason", "end_turn"),
                    usage=TokenUsage(**usage) if isinstance(usage, dict) else usage,
                    tool_calls=entry.response.get("tool_calls"),
                )

        return CompletionResponse(
            content="Default stub response.",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=10, output_tokens=20),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        response = await self.complete(request)
        yield CompletionChunk(delta=response.content, done=False)
        yield CompletionChunk(delta="", done=True)
