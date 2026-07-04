"""tests/test_telemetry.py — NullTelemetry, ConsoleTelemetry, OpenTelemetryProvider."""

from __future__ import annotations

import pytest

from ooagent.telemetry.console import ConsoleTelemetry
from ooagent.telemetry.null_telemetry import NullTelemetry
from ooagent.telemetry.otel import OpenTelemetryProvider


async def test_null_telemetry_span_returns_function_result_with_no_side_effects() -> None:
    telemetry = NullTelemetry()

    async def work() -> int:
        return 42

    assert await telemetry.span("test", work) == 42
    telemetry.counter("c")  # must not raise
    telemetry.gauge("g", 1.0)
    telemetry.histogram("h", 1.0)
    telemetry.event("e", {})


async def test_console_telemetry_span_reraises_on_failure(capsys) -> None:
    telemetry = ConsoleTelemetry()

    async def failing() -> None:
        raise ValueError("kaboom")

    with pytest.raises(ValueError):
        await telemetry.span("failing-span", failing)
    captured = capsys.readouterr()
    assert "failing-span" in captured.out


async def test_opentelemetry_provider_falls_back_gracefully_without_sdk() -> None:
    provider = OpenTelemetryProvider(service_name="test")

    async def work() -> str:
        return "ok"

    # Whether or not the opentelemetry SDK is installed, span() must still
    # run the wrapped function and return its result.
    result = await provider.span("test-span", work)
    assert result == "ok"
