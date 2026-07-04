"""plugins/opentelemetry/__init__.py — OpenTelemetryPlugin.

Contributes an ITelemetryProvider backed by the OpenTelemetry SDK. The
agent core never imports the `opentelemetry` package directly — all SDK
access is mediated through this plugin (DIP, OCP).

Note (judgment call): the TS source `plugins/opentelemetry/index.ts` defines
its own inline `OtelTelemetryProvider` and does NOT import the sibling
`telemetry/otel.ts` (which independently defines a *different* class,
`OpenTelemetryProvider`, with a different lazy-import/fallback strategy).
The two TS files duplicate similar OpenTelemetry bridging logic under
different names and are not wrapper/wrapped — they are separate. This file
is a faithful translation of `plugins/opentelemetry/index.ts` only; the
sibling `ooagent.telemetry.otel` module (Task 13) is unrelated and is not
imported here.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

from ooagent.core.protocols import IAgent, ITelemetryProvider, PluginContributions
from ooagent.plugins.base_plugin import AbstractPlugin

_logger = logging.getLogger("ooagent.plugins.opentelemetry")

T = TypeVar("T")


def _fire_and_forget(coro: Coroutine[Any, Any, None]) -> None:
    """Schedules `coro` without awaiting it.

    Duplicated from `ooagent.adapters.data.datastore_plugin._fire_and_forget`
    (same 10-line helper, kept local rather than cross-imported as a private
    symbol between packages). Python has no implicit always-on event loop —
    if one happens to be running we hand the coroutine to it as a background
    task; otherwise we run it to completion synchronously so it is never
    silently dropped.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
    else:
        loop.create_task(coro)


@dataclass(frozen=True)
class OtelPluginOptions:
    """`service_name`: reported to the collector. Default: 'ooagent'.
    `endpoint`: OTLP endpoint URL. Default: 'http://localhost:4318/v1/traces'.
    `provider`: inject a pre-configured ITelemetryProvider (for testing or
    custom setup). When provided, `endpoint` and `service_name` are ignored."""

    service_name: str = "ooagent"
    endpoint: str = "http://localhost:4318/v1/traces"
    provider: ITelemetryProvider | None = None


class OtelTelemetryProvider(ITelemetryProvider):
    """Concrete ITelemetryProvider backed by the `opentelemetry` SDK
    (lazy-imported). If the SDK is not installed, falls back to console
    (print) output with a warning — mirrors the TS dynamic-`import()`
    fallback so `opentelemetry` remains an optional dependency."""

    def __init__(self, service_name: str, endpoint: str) -> None:
        self._service_name = service_name
        self._endpoint = endpoint
        self._sdk: Any = None
        self._tracer: Any = None
        self._meter: Any = None

    async def init(self) -> None:
        try:
            # Lazy import — keeps `opentelemetry` an optional peer dependency.
            # `type: ignore[import-not-found, unused-ignore]` covers both cases:
            # the package missing (error) and the package installed, e.g. via
            # the `otel` extra (ignore would otherwise be flagged as unused).
            from opentelemetry import (  # type: ignore[import-not-found, unused-ignore]
                metrics,
                trace,
            )
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,  # type: ignore[import-not-found, unused-ignore]
            )
            from opentelemetry.sdk.resources import (
                Resource,  # type: ignore[import-not-found, unused-ignore]
            )
            from opentelemetry.sdk.trace import (
                TracerProvider,  # type: ignore[import-not-found, unused-ignore]
            )
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor,  # type: ignore[import-not-found, unused-ignore]
            )

            resource = Resource.create({"service.name": self._service_name})
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=self._endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            self._sdk = provider

            self._tracer = trace.get_tracer(self._service_name)
            self._meter = metrics.get_meter(self._service_name)
        except Exception:
            _logger.warning(
                "[OtelPlugin] opentelemetry packages not found — falling back to "
                "console telemetry. Install opentelemetry-sdk and the OTLP HTTP "
                "exporter to enable OTLP export."
            )

    async def shutdown(self) -> None:
        if self._sdk is not None:
            try:
                self._sdk.shutdown()
            except Exception as err:
                _logger.warning("[OtelPlugin] SDK shutdown error: %s", err)

    async def span(self, name: str, fn: Callable[[], Awaitable[T]]) -> T:
        if self._tracer is None:
            return await fn()
        span = self._tracer.start_span(name)
        try:
            result = await fn()
            self._set_status_ok(span)
            return result
        except Exception as err:
            self._set_status_error(span, str(err))
            raise
        finally:
            span.end()

    def counter(self, name: str, delta: float = 1) -> None:
        if self._meter is None:
            print(f"[otel.counter] {name} +{delta}")
            return
        self._meter.create_counter(name).add(delta)

    def gauge(self, name: str, value: float) -> None:
        if self._meter is None:
            print(f"[otel.gauge] {name} = {value}")
            return
        self._meter.create_observable_gauge(name)

    def histogram(self, name: str, value: float) -> None:
        if self._meter is None:
            print(f"[otel.histogram] {name} = {value}")
            return
        self._meter.create_histogram(name).record(value)

    def event(self, name: str, payload: dict[str, Any]) -> None:
        if self._tracer is None:
            print(f"[otel.event] {name} {payload}")
            return
        span = self._tracer.start_span(name)
        for k, v in payload.items():
            span.set_attribute(k, str(v))
        span.end()

    @staticmethod
    def _set_status_ok(span: Any) -> None:
        try:
            from opentelemetry.trace import (  # type: ignore[import-not-found, unused-ignore]
                Status,
                StatusCode,
            )

            span.set_status(Status(StatusCode.OK))
        except Exception:
            pass

    @staticmethod
    def _set_status_error(span: Any, message: str) -> None:
        try:
            from opentelemetry.trace import (  # type: ignore[import-not-found, unused-ignore]
                Status,
                StatusCode,
            )

            span.set_status(Status(StatusCode.ERROR, message))
        except Exception:
            pass


class OpenTelemetryPlugin(AbstractPlugin):
    plugin_id = "ooagent.opentelemetry"
    version = "1.0.0"

    def __init__(self, opts: OtelPluginOptions | None = None) -> None:
        self._opts = opts or OtelPluginOptions()
        self._provider: OtelTelemetryProvider | None = None

    # `IPlugin.on_register`/`on_dispose` are declared synchronous (-> None).
    # `OtelTelemetryProvider.init()`/`.shutdown()` are async (they lazy-import
    # and configure the `opentelemetry` SDK). `OOAgent.initialize()` calls
    # `plugin.on_register(self)` without `await` (it iterates a heterogeneous
    # list of mostly-synchronous IPlugins), so these methods stay genuinely
    # synchronous and hand the async init/shutdown work to `_fire_and_forget`,
    # which schedules it as a background task on a running loop or runs it to
    # completion via `asyncio.run` when no loop is active. This mirrors the
    # `DataStorePlugin.on_register`/`on_dispose` pattern in
    # `adapters/data/datastore_plugin.py`.
    def on_register(self, agent: IAgent[Any, Any]) -> None:
        if self._opts.provider is not None:
            return  # injected externally
        self._provider = OtelTelemetryProvider(self._opts.service_name, self._opts.endpoint)
        _fire_and_forget(self._provider.init())

    def on_dispose(self) -> None:
        if self._provider is not None:
            _fire_and_forget(self._provider.shutdown())
        self._provider = None

    def contributes(self) -> PluginContributions:
        # Note: ITelemetryProvider is injected at OOAgent construction time,
        # so this plugin exposes a getter for the consumer to wire it in.
        # Plugin contributes nothing to registries — the provider is
        # accessed via .telemetry_provider.
        return PluginContributions()

    @property
    def telemetry_provider(self) -> ITelemetryProvider | None:
        """The constructed provider — inject into OOAgent(telemetry=...)."""
        return self._opts.provider or self._provider
