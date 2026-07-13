"""tests/plugins/test_opentelemetry.py — OtelTelemetryProvider.gauge()."""

from __future__ import annotations

from typing import Any

from ooagent.plugins.opentelemetry import OtelTelemetryProvider


class _FakeMeter:
    def __init__(self) -> None:
        self.gauge_callbacks: dict[str, object] = {}

    def create_observable_gauge(
        self, name: str, callbacks: list[object]
    ) -> object:
        self.gauge_callbacks[name] = callbacks[0]
        return object()


def test_gauge_falls_back_to_print_when_meter_is_none(capsys: Any) -> None:
    provider = OtelTelemetryProvider("svc", "http://localhost:4318/v1/traces")
    provider.gauge("queue_depth", 5.0)
    captured = capsys.readouterr()
    assert "[otel.gauge] queue_depth = 5.0" in captured.out


def test_gauge_registers_an_observable_callback_reporting_the_last_set_value() -> None:
    provider = OtelTelemetryProvider("svc", "http://localhost:4318/v1/traces")
    provider._meter = _FakeMeter()

    provider.gauge("queue_depth", 5.0)
    callback = provider._meter.gauge_callbacks["queue_depth"]
    observations = list(callback(None))
    assert len(observations) == 1
    assert observations[0].value == 5.0

    provider.gauge("queue_depth", 9.0)
    observations = list(callback(None))
    assert observations[0].value == 9.0


def test_gauge_only_registers_the_instrument_once_per_name() -> None:
    provider = OtelTelemetryProvider("svc", "http://localhost:4318/v1/traces")
    provider._meter = _FakeMeter()

    provider.gauge("queue_depth", 1.0)
    provider.gauge("queue_depth", 2.0)
    provider.gauge("queue_depth", 3.0)

    assert len(provider._meter.gauge_callbacks) == 1
