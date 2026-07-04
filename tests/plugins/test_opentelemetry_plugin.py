"""tests/plugins/test_opentelemetry_plugin.py — OpenTelemetryPlugin fire-and-forget lifecycle.

Regression coverage for the bug where `OpenTelemetryPlugin.on_register`/
`.on_dispose` were declared `async def` while `IPlugin.on_register`/
`on_dispose` are synchronous and `OOAgent.initialize()` calls
`plugin.on_register(self)` WITHOUT `await`. Calling an async method
synchronously only constructs a coroutine object — its body never runs — so
`self._provider` stayed `None` forever and the OTel SDK never initialized.

These tests call `on_register`/`on_dispose` exactly the way
`OOAgent.initialize()`/`LifecycleManager.dispose()` do: synchronously, never
awaited. They assert the underlying async `init()`/`shutdown()` work
genuinely executes via the `_fire_and_forget` helper.
"""

from __future__ import annotations

import asyncio

from ooagent.core.protocols import ITelemetryProvider
from ooagent.plugins.opentelemetry import (
    OpenTelemetryPlugin,
    OtelPluginOptions,
    OtelTelemetryProvider,
)


class _FakeAgent:
    agent_id = "agent-1"


def test_on_register_runs_init_to_completion_when_no_event_loop_is_running(monkeypatch) -> None:
    """Mirrors a sync call site with no running loop: `_fire_and_forget` must
    fall back to `asyncio.run(coro)`, so `init()` completes before
    `on_register` returns."""
    calls: list[str] = []

    async def fake_init(self: OtelTelemetryProvider) -> None:
        calls.append("init")

    monkeypatch.setattr(OtelTelemetryProvider, "init", fake_init)

    plugin = OpenTelemetryPlugin()
    plugin.on_register(_FakeAgent())  # called synchronously, never awaited

    assert plugin._provider is not None
    assert calls == ["init"], "init() coroutine body must have actually executed"


async def test_on_register_schedules_init_as_background_task_on_running_loop(monkeypatch) -> None:
    """Inside a running event loop (the common case for an async test/app),
    `_fire_and_forget` must schedule `init()` as a background task rather
    than blocking; the task must still genuinely run to completion."""
    initialized = asyncio.Event()

    async def fake_init(self: OtelTelemetryProvider) -> None:
        initialized.set()

    monkeypatch.setattr(OtelTelemetryProvider, "init", fake_init)

    plugin = OpenTelemetryPlugin()
    plugin.on_register(_FakeAgent())  # called synchronously, never awaited

    assert plugin._provider is not None
    await asyncio.wait_for(initialized.wait(), timeout=1.0)


async def test_on_register_with_injected_provider_skips_construction() -> None:
    """When an `ITelemetryProvider` is injected via options, `on_register`
    must not construct or initialize an `OtelTelemetryProvider`."""

    class _StubProvider(ITelemetryProvider):
        async def span(self, name, fn):
            return await fn()

        def counter(self, name, delta=1.0):
            pass

        def gauge(self, name, value):
            pass

        def histogram(self, name, value):
            pass

        def event(self, name, payload):
            pass

    stub = _StubProvider()
    plugin = OpenTelemetryPlugin(OtelPluginOptions(provider=stub))
    plugin.on_register(_FakeAgent())

    assert plugin._provider is None
    assert plugin.telemetry_provider is stub


async def test_on_dispose_schedules_shutdown_and_clears_provider(monkeypatch) -> None:
    shut_down = asyncio.Event()

    async def fake_init(self: OtelTelemetryProvider) -> None:
        return None

    async def fake_shutdown(self: OtelTelemetryProvider) -> None:
        shut_down.set()

    monkeypatch.setattr(OtelTelemetryProvider, "init", fake_init)
    monkeypatch.setattr(OtelTelemetryProvider, "shutdown", fake_shutdown)

    plugin = OpenTelemetryPlugin()
    plugin.on_register(_FakeAgent())
    plugin.on_dispose()  # called synchronously, never awaited

    assert plugin._provider is None
    await asyncio.wait_for(shut_down.wait(), timeout=1.0)


def test_on_dispose_without_prior_register_is_a_noop() -> None:
    plugin = OpenTelemetryPlugin()
    plugin.on_dispose()  # must not raise even though _provider was never set
    assert plugin._provider is None
