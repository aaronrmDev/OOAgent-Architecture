"""telemetry/console.py — ConsoleTelemetry for development."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from ooagent.core.protocols import ITelemetryProvider

T = TypeVar("T")


class ConsoleTelemetry(ITelemetryProvider):
    def __init__(self, prefix: str = "[Telemetry]") -> None:
        self._prefix = prefix

    async def span(self, name: str, fn: Callable[[], Awaitable[T]]) -> T:
        start = time.monotonic()
        try:
            result = await fn()
            elapsed_ms = (time.monotonic() - start) * 1000
            print(f'{self._prefix} span "{name}" completed in {elapsed_ms:.0f}ms')
            return result
        except Exception as err:
            elapsed_ms = (time.monotonic() - start) * 1000
            print(f'{self._prefix} span "{name}" failed after {elapsed_ms:.0f}ms:', err)
            raise

    def counter(self, name: str, delta: float = 1) -> None:
        print(f'{self._prefix} counter "{name}" +{delta}')

    def gauge(self, name: str, value: float) -> None:
        print(f'{self._prefix} gauge "{name}" = {value}')

    def histogram(self, name: str, value: float) -> None:
        print(f'{self._prefix} histogram "{name}" {value}')

    def event(self, name: str, payload: dict[str, Any]) -> None:
        print(f'{self._prefix} event "{name}"', payload)
