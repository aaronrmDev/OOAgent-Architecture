# Plugin/Tool Bug Fixes & Conformance Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two real bugs (`OtelTelemetryProvider.gauge()` silently drops its value under a real SDK meter; `DateTimeTool` mislabels non-UTC timestamps with a `"Z"` UTC suffix), and add the two conformance suites CLAUDE.md §17 requires but the codebase is missing: an `IPlugin` conformance suite (`tests/conformance/test_plugin.py` does not exist) and `HttpFetchTool` coverage (currently untested beyond its name appearing in a `ToolKitPlugin` contributed-tools list).

**Architecture:** The `gauge()` fix registers one OTel `observable_gauge` instrument per metric name (created lazily, on first use) whose callback reads from a small `dict[str, float]` of last-set values updated synchronously on every `gauge()` call — the standard pattern for bridging a "set and forget" gauge API onto OTel's poll-based observable-instrument model. The `datetime_tool` fix only appends `"Z"` when the resolved timezone is literally `"UTC"`; any other IANA zone uses `datetime.isoformat()`'s real numeric offset. `test_plugin.py` follows this repo's existing conformance-suite shape (`tests/conformance/test_context.py`'s locally-defined-stub-then-parametrize style) across all 8 concrete `IPlugin` implementations. `HttpFetchTool` conformance uses `httpx.MockTransport` (via `monkeypatch`) so the suite stays fast and network-free, consistent with every other test in this repo.

**Tech Stack:** Python 3.11, `httpx.MockTransport` for offline HTTP testing, pytest + pytest-asyncio, mypy --strict, ruff. `opentelemetry-api`/`opentelemetry-sdk` are already installed in this project's `.venv` (the `otel` extra) — the gauge fix and its test exercise the real SDK meter, not the print-fallback branch.

## Global Constraints

- `mypy --strict` and `ruff` (`select = ["E", "F", "I", "UP", "B"]`, line-length 100) must pass on every touched file.
- No new runtime dependencies — `httpx` (already a base dependency) covers the `HttpFetchTool` test needs.
- Existing tests in `tests/plugins/test_tool_kit.py`, `tests/conformance/test_tool.py`, and any existing OTel plugin tests must continue to pass unmodified except where a task explicitly extends them.
- Do not weaken `HttpFetchTool`'s security boundary (HTTPS-only, allowlist check) while adding tests — these tests must exercise that boundary, not bypass it.

---

### Task 1: Fix `OtelTelemetryProvider.gauge()` — register a real observable-gauge callback

**Files:**
- Modify: `src/ooagent/plugins/opentelemetry/__init__.py:70-75` (`OtelTelemetryProvider.__init__`), `:143-147` (`gauge`)
- Test: `tests/plugins/test_opentelemetry.py` (create if it does not already exist)

**Interfaces:**
- Produces: `OtelTelemetryProvider.gauge(name: str, value: float) -> None` now registers (once per `name`, lazily) an `observable_gauge` instrument backed by a callback that reports the most recently set value, instead of discarding `value` entirely.

- [ ] **Step 1: Write the failing test**

Create `tests/plugins/test_opentelemetry.py` (or, if the file already exists, add these to it — check first):

```python
"""tests/plugins/test_opentelemetry.py — OtelTelemetryProvider.gauge()."""

from __future__ import annotations

from ooagent.plugins.opentelemetry import OtelTelemetryProvider


class _FakeMeter:
    def __init__(self) -> None:
        self.gauge_callbacks: dict[str, object] = {}

    def create_observable_gauge(self, name, callbacks):
        self.gauge_callbacks[name] = callbacks[0]
        return object()


def test_gauge_falls_back_to_print_when_meter_is_none(capsys) -> None:
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/plugins/test_opentelemetry.py -v`
Expected: FAIL — `_FakeMeter.create_observable_gauge` is never called with a `callbacks` kwarg by the current implementation (`self._meter.create_observable_gauge(name)`, no second argument), so `gauge_callbacks` stays empty and the second/third tests raise `KeyError`.

- [ ] **Step 3: Implement**

In `src/ooagent/plugins/opentelemetry/__init__.py`, replace `__init__` (lines 70-75):

```python
    def __init__(self, service_name: str, endpoint: str) -> None:
        self._service_name = service_name
        self._endpoint = endpoint
        self._sdk: Any = None
        self._tracer: Any = None
        self._meter: Any = None
```

with:

```python
    def __init__(self, service_name: str, endpoint: str) -> None:
        self._service_name = service_name
        self._endpoint = endpoint
        self._sdk: Any = None
        self._tracer: Any = None
        self._meter: Any = None
        self._gauge_values: dict[str, float] = {}
        self._gauge_instruments: dict[str, Any] = {}
```

Replace `gauge` (lines 143-147):

```python
    def gauge(self, name: str, value: float) -> None:
        if self._meter is None:
            print(f"[otel.gauge] {name} = {value}")
            return
        self._meter.create_observable_gauge(name)
```

with:

```python
    def gauge(self, name: str, value: float) -> None:
        if self._meter is None:
            print(f"[otel.gauge] {name} = {value}")
            return
        self._gauge_values[name] = value
        if name not in self._gauge_instruments:
            self._gauge_instruments[name] = self._meter.create_observable_gauge(
                name, callbacks=[self._make_gauge_callback(name)]
            )

    def _make_gauge_callback(self, name: str) -> Callable[[Any], Any]:
        def _callback(_options: Any) -> Any:
            from opentelemetry.metrics import (  # type: ignore[import-not-found, unused-ignore]
                Observation,
            )

            return [Observation(self._gauge_values[name])]

        return _callback
```

`Callable` is already imported at the top of the file (line 22: `from collections.abc import Awaitable, Callable, Coroutine`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/plugins/test_opentelemetry.py -v`
Expected: all PASS. If `Observation(value)` raises a `TypeError` about its constructor signature, check the installed `opentelemetry-api` version's actual `Observation` signature (`python -c "from opentelemetry.metrics import Observation; help(Observation)"`) and adjust the call to match (e.g. it may require `Observation(value, attributes={})` depending on version) — the callback-registration pattern (create once, callback reads a mutable dict) is the fix; the exact `Observation` constructor call is a one-line adjustment if the installed version differs from what this plan assumed.

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/plugins/opentelemetry/__init__.py tests/plugins/test_opentelemetry.py
git commit -m "fix(plugins): OtelTelemetryProvider.gauge() reports its value via a real observable callback"
```

---

### Task 2: Fix `DateTimeTool`'s non-UTC timezone mislabeling

**Files:**
- Modify: `src/ooagent/plugins/tool_kit/datetime_tool.py:31-41` (`DateTimeTool.execute`)
- Test: `tests/plugins/test_tool_kit.py`

**Interfaces:**
- Produces: `DateTimeTool.execute({"timezone": "America/New_York"})` now returns an `iso` string with the zone's real UTC offset (e.g. `...-04:00` or `...-05:00`) instead of a false `"Z"` suffix. The no-arg / `"UTC"` behavior is unchanged (still `"Z"`-suffixed) — the pre-existing test `test_datetime_tool_returns_iso_timestamp` must keep passing unmodified.

- [ ] **Step 1: Write the failing test**

Add to `tests/plugins/test_tool_kit.py`:

```python
import re


async def test_datetime_tool_returns_correct_numeric_offset_for_non_utc_timezone() -> None:
    tool = DateTimeTool()
    result = await tool.execute({"timezone": "America/New_York"})
    assert result["timezone"] == "America/New_York"
    assert not result["iso"].endswith("Z"), "non-UTC time must not be labeled with a UTC 'Z' suffix"
    assert re.search(r"[+-]\d{2}:\d{2}$", result["iso"]), result["iso"]


async def test_datetime_tool_still_returns_z_suffix_for_explicit_utc() -> None:
    tool = DateTimeTool()
    result = await tool.execute({"timezone": "UTC"})
    assert result["iso"].endswith("Z")
    assert result["timezone"] == "UTC"
```

(Add `import re` to the top of the file if not already present.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/plugins/test_tool_kit.py -v -k non_utc_timezone`
Expected: FAIL — `result["iso"]` currently ends with `"Z"` even for `"America/New_York"`, so both the `not ... endswith("Z")` assertion and the numeric-offset regex assertion fail.

- [ ] **Step 3: Implement**

In `src/ooagent/plugins/tool_kit/datetime_tool.py`, replace `execute` (lines 31-41):

```python
    async def execute(self, args: dict[str, Any]) -> Any:
        tz = args.get("timezone")
        if tz is None:
            tz = "UTC"
        try:
            now = datetime.now(ZoneInfo(tz))
            return {"iso": now.strftime("%Y-%m-%dT%H:%M:%S") + "Z", "timezone": tz}
        except Exception:
            now_utc = datetime.now(UTC)
            iso = now_utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now_utc.microsecond // 1000:03d}Z"
            return {"iso": iso, "timezone": "UTC"}
```

with:

```python
    async def execute(self, args: dict[str, Any]) -> Any:
        tz = args.get("timezone")
        if tz is None:
            tz = "UTC"
        try:
            now = datetime.now(ZoneInfo(tz))
            if tz == "UTC":
                iso = now.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
            else:
                iso = now.isoformat(timespec="seconds")
            return {"iso": iso, "timezone": tz}
        except Exception:
            now_utc = datetime.now(UTC)
            iso = now_utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now_utc.microsecond // 1000:03d}Z"
            return {"iso": iso, "timezone": "UTC"}
```

- [ ] **Step 4: Run tests to verify they pass, and confirm no regressions**

Run: `pytest tests/plugins/test_tool_kit.py -v`
Expected: all PASS, including the pre-existing `test_datetime_tool_returns_iso_timestamp` (no-arg call still defaults to `tz = "UTC"`, still hits the `if tz == "UTC":` branch, still `"Z"`-suffixed — unchanged behavior).

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/plugins/tool_kit/datetime_tool.py tests/plugins/test_tool_kit.py
git commit -m "fix(plugins): DateTimeTool no longer labels non-UTC times with a false 'Z' suffix"
```

---

### Task 3: Add `HttpFetchTool` conformance coverage

**Files:**
- Modify: `tests/conformance/test_tool.py`

**Interfaces:**
- Consumes: `HttpFetchTool`, `HttpFetchToolOptions` (`src/ooagent/plugins/tool_kit/http_fetch_tool.py`, existing, unmodified), `httpx.MockTransport` (existing `httpx` dependency).

- [ ] **Step 1: Write the failing tests**

Add to `tests/conformance/test_tool.py`:

```python
import httpx

from ooagent.plugins.tool_kit.http_fetch_tool import HttpFetchTool, HttpFetchToolOptions


def test_http_fetch_tool_name_and_description_are_non_empty() -> None:
    tool = HttpFetchTool()
    assert tool.name == "http_fetch"
    assert len(tool.description) > 0


def test_http_fetch_tool_to_vendor_spec_is_json_serializable() -> None:
    import json

    tool = HttpFetchTool()
    spec = tool.to_vendor_spec("anthropic")
    json.dumps(spec)  # must not raise


async def test_http_fetch_tool_rejects_non_https_url_without_network_call() -> None:
    tool = HttpFetchTool()
    with pytest.raises(ToolExecutionError):
        await tool.execute({"url": "http://example.com/data"})


async def test_http_fetch_tool_rejects_disallowed_host() -> None:
    tool = HttpFetchTool(HttpFetchToolOptions(allowed_hosts=["example.com"]))
    with pytest.raises(ToolExecutionError):
        await tool.execute({"url": "https://evil.example.org/data"})


async def test_http_fetch_tool_executes_successfully_against_a_mock_transport(monkeypatch) -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok", headers={"content-type": "text/plain"})

    real_async_client = httpx.AsyncClient

    def _mock_client(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(_handler)
        return real_async_client(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", _mock_client)

    tool = HttpFetchTool()
    result = await tool.execute({"url": "https://example.com/data"})
    assert result["status"] == 200
    assert result["body"] == "ok"
```

`pytest` and `ToolExecutionError` are already imported at the top of `tests/conformance/test_tool.py` (used by the existing `DateTimeTool`/`CalculatorTool` tests) — confirm before adding duplicate imports; add `import httpx` and the `HttpFetchTool`/`HttpFetchToolOptions` import to the top of the file alongside the existing tool imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/conformance/test_tool.py -v -k http_fetch`
Expected: FAIL with `ImportError: cannot import name 'HttpFetchTool'` from the test file (not yet imported) — confirms the tests are wired up before the import line is added; once the import line itself is added as part of Step 1, re-run to confirm the tests fail for a real reason first if the source has any surprises, then proceed. (In practice, `HttpFetchTool` and `HttpFetchToolOptions` already exist and are correct per the plan's fact-gathering — this step should reveal only import-ordering issues, if any, not source bugs.)

- [ ] **Step 3: N/A — no source implementation needed; `HttpFetchTool` itself is already correct**

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/conformance/test_tool.py -v`
Expected: all PASS, including the pre-existing `DateTimeTool`/`CalculatorTool` conformance tests and the 5 new `HttpFetchTool` tests. Confirm `test_http_fetch_tool_executes_successfully_against_a_mock_transport` does not make a real network call (it should complete in well under a second; if it hangs, the `monkeypatch.setattr` did not take effect before `HttpFetchTool.execute()` constructed its `httpx.AsyncClient`).

- [ ] **Step 5: Commit**

```bash
git add tests/conformance/test_tool.py
git commit -m "test(conformance): add HttpFetchTool coverage (name/description/vendor-spec/https-guard/allowlist/execute)"
```

---

### Task 4: Add an `IPlugin` conformance suite

**Files:**
- Create: `tests/conformance/test_plugin.py`

**Interfaces:**
- Consumes: `AuditPlugin`, `CachePlugin`, `LoggingPlugin`, `OpenTelemetryPlugin`+`OtelPluginOptions`, `RateLimitPlugin`, `ScopeGuardPlugin`, `SecurityPlugin`, `ToolKitPlugin` (all existing, zero-arg constructible except `OpenTelemetryPlugin`, which takes `OtelPluginOptions(provider=...)` to skip real SDK initialization during the test), `NULL_TELEMETRY` (existing singleton, `ooagent.core.agent`), `IAgent`/`ISessionState`/`Query`/`Artifact`/`PluginContributions` (existing, `ooagent.core.protocols`).

- [ ] **Step 1: Write the failing tests**

Create `tests/conformance/test_plugin.py`:

```python
"""tests/conformance/test_plugin.py — IPlugin conformance suite (§17 CLAUDE.md)."""

from __future__ import annotations

import pytest

from ooagent.core.agent import NULL_TELEMETRY
from ooagent.core.protocols import Artifact, IAgent, ISessionState, PluginContributions, Query
from ooagent.plugins.audit import AuditPlugin
from ooagent.plugins.cache import CachePlugin
from ooagent.plugins.logging import LoggingPlugin
from ooagent.plugins.opentelemetry import OpenTelemetryPlugin, OtelPluginOptions
from ooagent.plugins.rate_limit import RateLimitPlugin
from ooagent.plugins.scope_guard import ScopeGuardPlugin
from ooagent.plugins.security import SecurityPlugin
from ooagent.plugins.tool_kit import ToolKitPlugin


class _StubAgent(IAgent[Query, Artifact]):
    @property
    def agent_id(self) -> str:
        return "stub-agent"

    @property
    def state(self) -> ISessionState:
        raise NotImplementedError

    async def respond(self, query: Query) -> Artifact:
        raise NotImplementedError


def _all_plugins() -> list[object]:
    # Constructed fresh per call (not a module-level constant) so each test
    # gets its own plugin instances — on_dispose in one test must not affect
    # on_register in another.
    return [
        AuditPlugin(),
        CachePlugin(),
        LoggingPlugin(),
        OpenTelemetryPlugin(OtelPluginOptions(provider=NULL_TELEMETRY)),
        RateLimitPlugin(),
        ScopeGuardPlugin(),
        SecurityPlugin(),
        ToolKitPlugin(),
    ]


@pytest.mark.parametrize("plugin", _all_plugins(), ids=lambda p: p.plugin_id)
def test_plugin_id_and_version_are_non_empty_strings(plugin) -> None:
    assert isinstance(plugin.plugin_id, str) and plugin.plugin_id
    assert isinstance(plugin.version, str) and plugin.version


@pytest.mark.parametrize("plugin", _all_plugins(), ids=lambda p: p.plugin_id)
def test_plugin_contributes_returns_plugin_contributions(plugin) -> None:
    assert isinstance(plugin.contributes(), PluginContributions)


@pytest.mark.parametrize("plugin", _all_plugins(), ids=lambda p: p.plugin_id)
def test_plugin_on_register_does_not_raise(plugin) -> None:
    plugin.on_register(_StubAgent())


@pytest.mark.parametrize("plugin", _all_plugins(), ids=lambda p: p.plugin_id)
def test_plugin_on_dispose_is_idempotent(plugin) -> None:
    plugin.on_dispose()
    plugin.on_dispose()  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail (or reveal import issues)**

Run: `pytest tests/conformance/test_plugin.py -v`
Expected: at this point the file is new, so a first run either passes immediately (all 8 plugins already satisfy the `IPlugin` contract per the fact-gathering behind this plan) or fails on an import path — e.g. if a plugin's public class is not actually re-exported from its package `__init__.py` under the name assumed here. Treat any `ImportError` as a signal to check the real export name in that plugin's `__init__.py` (all 8 were confirmed importable this way during planning; a failure here means the package changed since).

- [ ] **Step 3: Fix any import-path or construction issues found in Step 2**

If a plugin's constructor turns out not to be zero-arg (contradicting the fact-gathering behind this plan), pass its documented no-op `*Options` dataclass explicitly, matching the `OpenTelemetryPlugin` pattern above (e.g. `RateLimitPlugin(RateLimitOptions())` instead of `RateLimitPlugin()`), and re-run.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/conformance/test_plugin.py -v`
Expected: all 32 parametrized tests PASS (8 plugins × 4 test functions).

Run: `pytest tests/plugins/ tests/conformance/ -v`
Expected: all PASS — no interference between this new suite and the existing per-plugin behavior tests in `tests/plugins/`.

- [ ] **Step 5: Commit**

```bash
git add tests/conformance/test_plugin.py
git commit -m "test(conformance): add IPlugin conformance suite covering all 8 concrete plugins"
```

---

### Task 5: Full-suite regression check and static analysis

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all PASS.

- [ ] **Step 2: Run mypy --strict**

Run: `mypy --strict src/ooagent`
Expected: no errors. Pay attention to the lazy `Observation` import in `opentelemetry/__init__.py`'s new `_make_gauge_callback` (should carry the same `# type: ignore[import-not-found, unused-ignore]` pattern already used elsewhere in that file), and to `_StubAgent(IAgent[Query, Artifact])`'s full abstract-method coverage in `test_plugin.py`.

- [ ] **Step 3: Run ruff**

Run: `ruff check src/ooagent tests`
Expected: no errors.

- [ ] **Step 4: Commit if any lint-only fixups were needed**

```bash
git add -A
git commit -m "chore: lint/type fixups for plugin/tool bug fixes and conformance work"
```

(Skip this commit entirely if steps 1-3 were already clean.)
