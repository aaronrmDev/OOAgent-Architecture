"""telemetry/otel.py — OpenTelemetry ITelemetryProvider adapter.

Optional dependency: pip install opentelemetry-api opentelemetry-sdk
Without the package installed, this provider silently no-ops.

The TS source keeps the OTel package optional by dynamically `import()`-ing
it at construction time and swallowing the failure. Python's `import` is
synchronous, so the equivalent optional-dependency pattern is a plain
try/except ImportError performed once at module load — there is no
async-loading race to reproduce.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from ooagent.core.protocols import ITelemetryProvider

T = TypeVar("T")

try:
    from opentelemetry import metrics as _otel_metrics
    from opentelemetry import trace as _otel_trace
    from opentelemetry.metrics import Observation as _OTelObservation
    from opentelemetry.trace import Status as _OTelStatus
    from opentelemetry.trace import StatusCode as _OTelStatusCode
except ImportError:  # pragma: no cover - optional dependency not installed
    _otel_trace = None
    _otel_metrics = None
    _OTelObservation = None
    _OTelStatus = None
    _OTelStatusCode = None


class OpenTelemetryProvider(ITelemetryProvider):
    def __init__(self, service_name: str = "ooagent") -> None:
        self._service_name = service_name
        self._available = _otel_trace is not None and _otel_metrics is not None

    async def span(self, name: str, fn: Callable[[], Awaitable[T]]) -> T:
        if not self._available:
            return await fn()

        tracer = _otel_trace.get_tracer(self._service_name)
        with tracer.start_as_current_span(name) as span:
            try:
                result = await fn()
                span.set_status(_OTelStatus(_OTelStatusCode.OK))
                return result
            except Exception as err:
                span.set_status(_OTelStatus(_OTelStatusCode.ERROR, str(err)))
                span.record_exception(err)
                raise

    def counter(self, name: str, delta: float = 1) -> None:
        if not self._available:
            return
        meter = _otel_metrics.get_meter(self._service_name)
        meter.create_counter(name).add(delta)

    def gauge(self, name: str, value: float) -> None:
        if not self._available:
            return
        meter = _otel_metrics.get_meter(self._service_name)

        def _callback(_options: Any) -> list[Any]:
            return [_OTelObservation(value)]

        meter.create_observable_gauge(name, callbacks=[_callback])

    def histogram(self, name: str, value: float) -> None:
        if not self._available:
            return
        meter = _otel_metrics.get_meter(self._service_name)
        meter.create_histogram(name).record(value)

    def event(self, name: str, payload: dict[str, Any]) -> None:
        if not self._available:
            return
        span = _otel_trace.get_current_span()
        span.add_event(name, attributes=payload)
