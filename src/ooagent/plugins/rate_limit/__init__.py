"""plugins/rate_limit/__init__.py — RateLimitPlugin.

Wraps every registered ITool with a rate-limiting adapter that enforces a
per-tool call budget (calls per window).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

from ooagent.core.protocols import (
    IAgent,
    ITool,
    JSONSchema,
    LLMVendor,
    PluginContributions,
    ToolExecutionError,
    VendorToolSpec,
)
from ooagent.plugins.base_plugin import AbstractPlugin


@dataclass(frozen=True)
class RateLimitOptions:
    """`max_calls`: maximum calls allowed per window. Default: 60.
    `window_ms`: window duration in milliseconds. Default: 60 000 (1 minute)."""

    max_calls: int = 60
    window_ms: int = 60_000


class RateLimitedTool(ITool):
    """Wraps an ITool and enforces a sliding-window call budget."""

    def __init__(self, inner: ITool, max_calls: int, window_ms: int) -> None:
        self._inner = inner
        self._max_calls = max_calls
        self._window_ms = window_ms
        self._calls: list[float] = []

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
        now = time.time() * 1000
        self._calls = [t for t in self._calls if now - t < self._window_ms]

        if len(self._calls) >= self._max_calls:
            oldest_call = self._calls[0]
            retry_after_ms = self._window_ms - (now - oldest_call)
            raise ToolExecutionError(
                self._inner.name,
                args,
                Exception(
                    f"Rate limit exceeded ({self._max_calls} calls/{self._window_ms}ms). "
                    f"Retry after {math.ceil(retry_after_ms / 1000)}s."
                ),
            )

        self._calls.append(now)
        return await self._inner.execute(args)


class RateLimitPlugin(AbstractPlugin):
    plugin_id = "ooagent.rate-limit"
    version = "1.0.0"

    def __init__(self, opts: RateLimitOptions | None = None) -> None:
        opts = opts or RateLimitOptions()
        self._max_calls = opts.max_calls
        self._window_ms = opts.window_ms
        self._tools_to_wrap: list[ITool] = []

    def wrap_tools(self, *tools: ITool) -> RateLimitPlugin:
        """Call before initialize() to declare which tools to wrap.
        If no tools are provided, no wrapping occurs at contributes() time."""
        self._tools_to_wrap = list(tools)
        return self

    def on_register(self, agent: IAgent[Any, Any]) -> None:
        return None

    def on_dispose(self) -> None:
        self._tools_to_wrap = []

    def contributes(self) -> PluginContributions:
        wrapped: list[ITool] = [
            RateLimitedTool(t, self._max_calls, self._window_ms) for t in self._tools_to_wrap
        ]
        return PluginContributions(tools=wrapped)
