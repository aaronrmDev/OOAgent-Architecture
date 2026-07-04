"""tests/conformance/test_llm_client.py — ILLMClient conformance suite (§17 CLAUDE.md).

Uses StubLLMClient — the deterministic test double (§17: use StubLLMClient
for unit tests).
"""

from __future__ import annotations

import pytest

from ooagent.core.protocols import CompletionRequest, Message, TokenLimitError

from ..stub_llm_client import StubLLMClient

client = StubLLMClient(max_tokens=100)

valid_request = CompletionRequest(
    messages=[Message(role="user", content="hello")],
    max_tokens=50,
    temperature=0,
)

oversized_request = CompletionRequest(
    messages=[Message(role="user", content="x" * 500)],
    max_tokens=200,
    temperature=0,
)


async def test_complete_valid_request_returns_a_completion_response() -> None:
    response = await client.complete(valid_request)
    assert isinstance(response.content, str), (
        "CompletionResponse.content must be a string"
    )
    assert len(response.stop_reason) > 0, (
        "CompletionResponse.stop_reason must be non-empty"
    )
    assert response.usage.input_tokens >= 0, "usage.input_tokens must be >= 0"
    assert response.usage.output_tokens >= 0, "usage.output_tokens must be >= 0"


async def test_complete_oversized_request_throws_token_limit_error() -> None:
    with pytest.raises(TokenLimitError):
        await client.complete(oversized_request)


async def test_stream_yields_at_least_one_chunk_before_resolving() -> None:
    chunks: list[object] = []
    async for chunk in client.stream(valid_request):
        chunks.append(chunk)
    assert len(chunks) >= 1, "stream() must yield at least one chunk before done"


def test_model_id_and_max_tokens_are_exposed_on_the_client() -> None:
    assert len(client.model_id) > 0, "ILLMClient.model_id must be non-empty"
    assert client.max_tokens > 0, "ILLMClient.max_tokens must be > 0"
    assert isinstance(client.supports_tools, bool), (
        "supports_tools must be boolean"
    )
