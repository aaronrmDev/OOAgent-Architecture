"""adapters/llm/caching_proxy.py — CachingLLMProxy and ThrottlingLLMProxy (Proxy pattern)."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from ooagent.core.protocols import (
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    ILLMClient,
    LLMVendor,
)


class CachingLLMProxy(ILLMClient):
    """Proxy — caches deterministic completions — §4 GoF."""

    def __init__(self, inner: ILLMClient) -> None:
        self._inner = inner
        self._cache: dict[str, CompletionResponse] = {}

    @property
    def vendor(self) -> LLMVendor:
        return self._inner.vendor

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    @property
    def max_tokens(self) -> int:
        return self._inner.max_tokens

    @property
    def supports_tools(self) -> bool:
        return self._inner.supports_tools

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        # Only cache deterministic requests (no tools, temperature 0 or unset).
        cacheable = not request.tools and (
            (request.temperature if request.temperature is not None else 0) == 0
        )
        if not cacheable:
            return await self._inner.complete(request)

        key = self._cache_key(request)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        result = await self._inner.complete(request)
        self._cache[key] = result
        return result

    async def ping(self) -> bool:
        return await self._inner.ping()

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        async for chunk in self._inner.stream(request):
            yield chunk

    def clear_cache(self) -> None:
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def _cache_key(self, request: CompletionRequest) -> str:
        payload = {
            "model": self._inner.model_id,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_tokens": request.max_tokens,
        }
        return json.dumps(payload)


@dataclass(frozen=True)
class ThrottlingOptions:
    requests_per_minute: int


class ThrottlingLLMProxy(ILLMClient):
    """Proxy — enforces rate limits transparently — §4 GoF."""

    def __init__(self, inner: ILLMClient, options: ThrottlingOptions) -> None:
        self._inner = inner
        self._options = options
        self._tokens = options.requests_per_minute
        self._last_refill = time.monotonic()

    @property
    def vendor(self) -> LLMVendor:
        return self._inner.vendor

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    @property
    def max_tokens(self) -> int:
        return self._inner.max_tokens

    @property
    def supports_tools(self) -> bool:
        return self._inner.supports_tools

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        await self._throttle()
        return await self._inner.complete(request)

    async def ping(self) -> bool:
        return await self._inner.ping()

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        await self._throttle()
        async for chunk in self._inner.stream(request):
            yield chunk

    async def _throttle(self) -> None:
        self._refill()
        if self._tokens <= 0:
            seconds_per_token = 60.0 / self._options.requests_per_minute
            await asyncio.sleep(seconds_per_token)
            self._refill()
        self._tokens -= 1

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        refill = int((elapsed / 60.0) * self._options.requests_per_minute)
        if refill > 0:
            self._tokens = min(self._options.requests_per_minute, self._tokens + refill)
            self._last_refill = now
