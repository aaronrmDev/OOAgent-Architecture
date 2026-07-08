"""tests/adapters/llm/test_throttling_proxy.py — ThrottlingLLMProxy (zero prior coverage)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

import pytest

from ooagent.adapters.llm.caching_proxy import ThrottlingLLMProxy, ThrottlingOptions
from ooagent.core.protocols import (
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    ILLMClient,
    LLMVendor,
    Message,
    TokenUsage,
)


class _StubInnerClient(ILLMClient):
    def __init__(self) -> None:
        self.complete_calls = 0
        self.stream_calls = 0

    @property
    def vendor(self) -> LLMVendor:
        return "anthropic"

    @property
    def model_id(self) -> str:
        return "stub-model"

    @property
    def max_tokens(self) -> int:
        return 4096

    @property
    def supports_tools(self) -> bool:
        return False

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.complete_calls += 1
        return CompletionResponse(
            content="stub response",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        self.stream_calls += 1
        yield CompletionChunk(delta="stub", done=False)
        yield CompletionChunk(delta="", done=True)


def test_throttling_proxy_delegates_vendor_and_config_properties_to_inner() -> None:
    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    assert proxy.vendor == inner.vendor
    assert proxy.model_id == inner.model_id
    assert proxy.max_tokens == inner.max_tokens
    assert proxy.supports_tools == inner.supports_tools


async def test_throttling_proxy_complete_delegates_to_inner_client() -> None:
    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    response = await proxy.complete(
        CompletionRequest(messages=[Message(role="user", content="hi")])
    )
    assert response.content == "stub response"
    assert inner.complete_calls == 1


async def test_throttling_proxy_stream_delegates_to_inner_client() -> None:
    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    chunks = [
        chunk
        async for chunk in proxy.stream(
            CompletionRequest(messages=[Message(role="user", content="hi")])
        )
    ]
    assert chunks[-1].done is True
    assert inner.stream_calls == 1


async def test_throttling_proxy_does_not_sleep_when_tokens_available() -> None:
    """A fresh proxy starts with a full token bucket (_tokens ==
    requests_per_minute) — a single request must not trigger the
    sleep-based throttle path in _throttle()."""
    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    start = time.monotonic()
    await proxy.complete(CompletionRequest(messages=[Message(role="user", content="hi")]))
    elapsed = time.monotonic() - start
    assert elapsed < 0.5


async def test_throttling_proxy_sleeps_when_token_bucket_is_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the token bucket is exhausted, _throttle() must actually
    invoke asyncio.sleep() with the bucket's per-token duration —
    monkeypatched here (rather than left to really sleep) so the test
    stays fast and deterministic (CLAUDE.md §17)."""
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    proxy._tokens = 0  # type: ignore[attr-defined]  # force the exhausted-bucket path

    await proxy.complete(CompletionRequest(messages=[Message(role="user", content="hi")]))

    assert sleep_calls == [1.0]  # 60.0 / requests_per_minute(60) == 1.0


def test_refill_replenishes_tokens_proportional_to_elapsed_time() -> None:
    """White-box test of _refill()'s token-bucket math, asserted directly
    against internal state rather than by actually sleeping — keeps this
    test fast and deterministic (CLAUDE.md §17)."""
    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    proxy._tokens = 0  # type: ignore[attr-defined]
    proxy._last_refill -= 30.0  # type: ignore[attr-defined]  # simulate 30s elapsed
    proxy._refill()  # type: ignore[attr-defined]
    # 60 requests/minute * (30s / 60s) = 30 tokens refilled
    assert proxy._tokens == 30  # type: ignore[attr-defined]


def test_refill_caps_tokens_at_requests_per_minute() -> None:
    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    proxy._tokens = 50  # type: ignore[attr-defined]
    proxy._last_refill -= 120.0  # type: ignore[attr-defined]  # simulate 2 minutes elapsed
    proxy._refill()  # type: ignore[attr-defined]
    assert proxy._tokens == 60  # type: ignore[attr-defined]
