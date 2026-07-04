"""plugins/cache/__init__.py — CachePlugin.

Contributes a CachingLLMProxy-compatible tool-level cache. Caches
deterministic tool results (idempotent tools) by (name, stable-JSON-args).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from ooagent.core.protocols import (
    ITool,
    JSONSchema,
    LLMVendor,
    PluginContributions,
    VendorToolSpec,
)
from ooagent.plugins.base_plugin import AbstractPlugin


@dataclass(frozen=True)
class CachePluginOptions:
    """`max_entries`: maximum cached entries per tool. Default: 256.
    `ttl_ms`: TTL for cached entries in milliseconds. Default: 300 000 (5 min)."""

    max_entries: int = 256
    ttl_ms: int = 300_000


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class CachedTool(ITool):
    """Wraps an ITool with an in-process LRU-TTL cache for deterministic calls."""

    def __init__(self, inner: ITool, max_entries: int, ttl_ms: int) -> None:
        self._inner = inner
        self._max_entries = max_entries
        self._ttl_ms = ttl_ms
        self._cache: dict[str, _CacheEntry] = {}

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def description(self) -> str:
        return self._inner.description

    def input_schema(self) -> JSONSchema:
        return self._inner.input_schema()

    def to_vendor_spec(self, vendor: LLMVendor) -> VendorToolSpec:
        return self._inner.to_vendor_spec(vendor)

    async def execute(self, args: dict[str, Any]) -> Any:
        key = self._cache_key(args)
        now = time.time() * 1000
        hit = self._cache.get(key)

        if hit is not None and hit.expires_at > now:
            return hit.value

        result = await self._inner.execute(args)
        self._evict_if_needed()
        self._cache[key] = _CacheEntry(value=result, expires_at=now + self._ttl_ms)
        return result

    def _cache_key(self, args: dict[str, Any]) -> str:
        return json.dumps({k: args[k] for k in sorted(args)}, sort_keys=True, default=str)

    def _evict_if_needed(self) -> None:
        if len(self._cache) < self._max_entries:
            return
        # Evict oldest entry — plain dicts preserve insertion order (insertion-order LRU)
        oldest = next(iter(self._cache), None)
        if oldest is not None:
            del self._cache[oldest]

    def flush(self) -> None:
        """Clears the entire cache for this tool."""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


class CachePlugin(AbstractPlugin):
    plugin_id = "ooagent.cache"
    version = "1.0.0"

    def __init__(self, opts: CachePluginOptions | None = None) -> None:
        opts = opts or CachePluginOptions()
        self._max_entries = opts.max_entries
        self._ttl_ms = opts.ttl_ms
        self._tools_to_cache: list[ITool] = []
        self._cached_tools: list[CachedTool] = []

    def cache_tools(self, *tools: ITool) -> CachePlugin:
        """Declare which tools should have their results cached."""
        self._tools_to_cache = list(tools)
        return self

    def on_dispose(self) -> None:
        for t in self._cached_tools:
            t.flush()
        self._cached_tools = []
        self._tools_to_cache = []

    def contributes(self) -> PluginContributions:
        self._cached_tools = [
            CachedTool(t, self._max_entries, self._ttl_ms) for t in self._tools_to_cache
        ]
        return PluginContributions(tools=list(self._cached_tools))

    def flush_all(self) -> None:
        """Flush all caches. Useful in tests or after context switches."""
        for t in self._cached_tools:
            t.flush()

    @property
    def total_cached_entries(self) -> int:
        """Returns the total number of cached entries across all tools."""
        return sum(t.size for t in self._cached_tools)
