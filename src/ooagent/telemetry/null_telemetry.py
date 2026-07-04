"""telemetry/null_telemetry.py — NullTelemetry (Null Object — default for unit tests)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from ooagent.core.protocols import ITelemetryProvider

T = TypeVar("T")


class NullTelemetry(ITelemetryProvider):
    async def span(self, name: str, fn: Callable[[], Awaitable[T]]) -> T:
        return await fn()

    def counter(self, name: str, delta: float = 1) -> None:
        pass

    def gauge(self, name: str, value: float) -> None:
        pass

    def histogram(self, name: str, value: float) -> None:
        pass

    def event(self, name: str, payload: dict[str, Any]) -> None:
        pass
