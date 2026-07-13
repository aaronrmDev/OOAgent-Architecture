"""examples/_common.py — DemoLLMClient: a deterministic ILLMClient shared
by the golden-path examples so each one runs with zero API keys and zero
network access. Not part of the installed ooagent package's public API
(src/ooagent/) — this is example-only scaffolding, the same role
tests/stub_llm_client.py plays for the test suite (CLAUDE.md §7 keeps
test/example doubles out of src/).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ooagent.core.protocols import (
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    ILLMClient,
    LLMVendor,
    TokenUsage,
)


class DemoLLMClient(ILLMClient):
    """Always returns the same scripted response — deterministic, offline."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    @property
    def model_id(self) -> str:
        return "demo-1.0"

    @property
    def vendor(self) -> LLMVendor:
        return "anthropic"  # arbitrary — any valid LLMVendor works for this deterministic stand-in

    @property
    def max_tokens(self) -> int:
        return 4096

    @property
    def supports_tools(self) -> bool:
        return False

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            content=self._response_text,
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=10, output_tokens=20),
        )

    async def ping(self) -> bool:
        return True

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        yield CompletionChunk(delta=self._response_text, done=False)
        yield CompletionChunk(delta="", done=True)
