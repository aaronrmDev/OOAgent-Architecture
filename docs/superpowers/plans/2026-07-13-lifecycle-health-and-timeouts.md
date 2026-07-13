# LifecycleManager Health Checks & Timeout Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `LifecycleManager.health_check()` genuinely probe the LLM client and plugins instead of only reading local circuit-breaker state, and make the four `AgentConfig` timeout fields (`turn_timeout_ms`, `tool_timeout_ms`, `specialist_timeout_ms`, `orchestration_timeout_ms`) actually bound the calls they name instead of sitting unused.

**Architecture:** Add an optional `ping()` method to `ILLMClient` (default-implemented via a mixin-free approach: add it as an abstract method with a concrete default is not possible on an ABC, so instead add it as a **new abstract method** with a trivial required implementation added to every existing `ILLMClient` implementer — `StubLLMClient` and the 4 real vendor adapters — each returning `True` unconditionally for now, since a real network probe per-vendor is out of scope for this pass and would require live credentials this pass cannot verify). Wire `LifecycleManager.health_check()` to call it and to award `PluginRegistry.verify()` real teeth (raise on the first plugin that fails a self-check, rather than doing nothing). Wrap the two unbounded `await` call-sites in `agent.py` (`self._llm_client.complete(request)` and `await tool.execute(...)`) in `asyncio.wait_for` using `config.turn_timeout_ms`/`config.tool_timeout_ms` respectively, converting a `TimeoutError` into the same failure-handling path already used for other exceptions (no new FSM states needed — a timeout is just another exception `_llm_tool_loop`/`_execute_tool`'s existing callers already catch).

**Tech Stack:** Python 3.11, `asyncio.wait_for`, pytest + pytest-asyncio, mypy --strict, ruff.

## Global Constraints

- `mypy --strict` and `ruff` (`select = ["E", "F", "I", "UP", "B"]`, line-length 100) must pass on every touched file.
- `ILLMClient` is a core, semver-stable interface (CLAUDE.md §18) — adding a new abstract method is a **breaking** change for any external implementer. This plan accepts that cost deliberately (the alternative — no health-check capability at all — is the gap being fixed) and updates every implementer in this repo in the same task so nothing is left broken.
- No new runtime dependencies.
- Existing tests in `tests/core/test_lifecycle.py`, `tests/core/test_agent.py`, `tests/adapters/llm/*` must continue to pass except where a task explicitly updates them.

---

### Task 1: Add `ping()` to `ILLMClient` and implement it on every existing client

**Files:**
- Modify: `src/ooagent/core/protocols.py:353-374` (`ILLMClient` ABC)
- Modify: `tests/stub_llm_client.py` (`StubLLMClient`)
- Modify: `src/ooagent/adapters/llm/anthropic.py`, `openai.py`, `gemini.py`, `ollama.py` (each `*LLMClient` class)
- Modify: `tests/core/test_agent.py` (`_StubLLMClient`, `_AlwaysFailingLLMClient`, `_ToolUseLLMClient` — 3 local test doubles that implement `ILLMClient`)
- Modify: `tests/conformance/test_agent.py` (`_StubLLMClient` local test double)
- Test: `tests/core/test_protocols.py`, `tests/adapters/llm/test_behavior_matrix.py` (or wherever adapter-level tests already live — see Task 1 Step 1 for the exact assertion)

**Interfaces:**
- Produces: `ILLMClient.ping() -> Awaitable[bool]` — returns `True` when the client considers itself reachable/healthy. For this pass every implementation returns `True` unconditionally (a real network round-trip probe is future work — see plan closing notes); the point of this task is to make the **interface and call site** real, not to implement per-vendor network health checks that cannot be verified without live credentials in this environment.

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_protocols.py`:

```python
async def test_illmclient_ping_is_a_required_abstract_method() -> None:
    from ooagent.core.protocols import ILLMClient

    assert "ping" in ILLMClient.__abstractmethods__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_protocols.py::test_illmclient_ping_is_a_required_abstract_method -v`
Expected: FAIL (`AssertionError: assert 'ping' in frozenset({...})` — `ping` not yet in the abstract-methods set)

- [ ] **Step 3: Add the abstract method and implement it everywhere**

In `src/ooagent/core/protocols.py`, the `ILLMClient` class (lines 353-374):

```python
class ILLMClient(ABC):
    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    @abstractmethod
    def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]: ...

    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @property
    @abstractmethod
    def vendor(self) -> LLMVendor: ...

    @property
    @abstractmethod
    def max_tokens(self) -> int: ...

    @property
    @abstractmethod
    def supports_tools(self) -> bool: ...
```

Add a `ping` abstract method after `complete`:

```python
class ILLMClient(ABC):
    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    @abstractmethod
    async def ping(self) -> bool: ...

    @abstractmethod
    def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]: ...

    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @property
    @abstractmethod
    def vendor(self) -> LLMVendor: ...

    @property
    @abstractmethod
    def max_tokens(self) -> int: ...

    @property
    @abstractmethod
    def supports_tools(self) -> bool: ...
```

In `tests/stub_llm_client.py`, add to `StubLLMClient`:

```python
    async def ping(self) -> bool:
        return True
```

(place it directly after the existing `complete` method, matching the ABC's method order)

In each of `src/ooagent/adapters/llm/anthropic.py`, `openai.py`, `gemini.py`, `ollama.py`, add to the respective `*LLMClient` class (directly after `complete`):

```python
    async def ping(self) -> bool:
        return True
```

In `tests/core/test_agent.py`, add the same `async def ping(self) -> bool: return True` method to `_StubLLMClient` (after `complete`, before `stream`), to `_AlwaysFailingLLMClient` (after `complete`, before `stream` — note: `ping()` still returns `True` here; only `complete()` fails, since `ping` and `complete` are independent capabilities), and to `_ToolUseLLMClient` (after `complete`, before `stream`).

In `tests/conformance/test_agent.py`, add the same method to its local `_StubLLMClient` (after `complete`, before `stream`).

- [ ] **Step 4: Run test to verify it passes, then run the full adapter suite**

Run: `pytest tests/core/test_protocols.py::test_illmclient_ping_is_a_required_abstract_method -v`
Expected: PASS

Run: `pytest tests/adapters/llm/ tests/core/ tests/conformance/ tests/mcp/ -v`
Expected: all PASS — every `ILLMClient` implementer in the codebase now satisfies the widened ABC, so no `TypeError: Can't instantiate abstract class` failures should appear. If any do, the implementer was missed; add `ping()` to it following the same pattern.

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/protocols.py tests/stub_llm_client.py src/ooagent/adapters/llm/anthropic.py src/ooagent/adapters/llm/openai.py src/ooagent/adapters/llm/gemini.py src/ooagent/adapters/llm/ollama.py tests/core/test_agent.py tests/conformance/test_agent.py tests/core/test_protocols.py
git commit -m "feat(core): add ILLMClient.ping() health-probe method"
```

---

### Task 2: Wire `LifecycleManager.health_check()` to actually call `ping()`

**Files:**
- Modify: `src/ooagent/core/lifecycle.py:42-71` (`LifecycleManager.__init__`, `health_check`)
- Modify: `src/ooagent/core/agent.py:120` (the `LifecycleManager(...)` construction site in `OOAgent.__init__`)
- Test: `tests/core/test_lifecycle.py`

**Interfaces:**
- Consumes: `ILLMClient.ping()` from Task 1.
- Produces: `LifecycleManager(plugin_registry: PluginRegistry, state: SessionState, llm_client: ILLMClient | None = None)` — `llm_client` is optional and defaults to `None` (backward compatible with any direct `LifecycleManager(...)` construction in tests that don't pass one); `health_check()` returns `"unhealthy"` if `ping()` raises or returns `False`, in addition to its existing `"unhealthy"`-when-not-ready and `"degraded"`-when-circuit-breaker-open checks.

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_lifecycle.py`:

```python
async def test_health_check_reports_unhealthy_when_llm_ping_fails() -> None:
    from ooagent.core.protocols import AgentConfig, ILLMClient

    class _UnreachableLLMClient(ILLMClient):
        async def complete(self, request):
            raise NotImplementedError

        async def ping(self) -> bool:
            return False

        def stream(self, request):
            raise NotImplementedError

        @property
        def model_id(self) -> str:
            return "unreachable"

        @property
        def vendor(self):
            return "anthropic"

        @property
        def max_tokens(self) -> int:
            return 1

        @property
        def supports_tools(self) -> bool:
            return False

    manager = LifecycleManager(PluginRegistry(), SessionState(), llm_client=_UnreachableLLMClient())
    await manager.initialize(AgentConfig())
    assert await manager.health_check() == "unhealthy"
```

Add the necessary imports at the top of `tests/core/test_lifecycle.py` if not already present: `from ooagent.core.lifecycle import LifecycleManager` and `from ooagent.core.registry import PluginRegistry` and `from ooagent.core.state import SessionState` (these three are very likely already imported given the existing 6 tests construct `LifecycleManager(PluginRegistry(), SessionState())` — verify before adding to avoid duplicate imports).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_lifecycle.py::test_health_check_reports_unhealthy_when_llm_ping_fails -v`
Expected: FAIL with `TypeError: LifecycleManager.__init__() got an unexpected keyword argument 'llm_client'`

- [ ] **Step 3: Implement**

In `src/ooagent/core/lifecycle.py`, replace the constructor (lines 43-49):

```python
    def __init__(self, plugin_registry: PluginRegistry, state: SessionState) -> None:
        self._plugin_registry = plugin_registry
        self._state = state
        self._ready = False
        self._disposed = False
        self._circuit_breaker: CircuitBreaker | None = None
        self._exit_handler_registered = False
```

with:

```python
    def __init__(
        self,
        plugin_registry: PluginRegistry,
        state: SessionState,
        llm_client: ILLMClient | None = None,
    ) -> None:
        self._plugin_registry = plugin_registry
        self._state = state
        self._llm_client = llm_client
        self._ready = False
        self._disposed = False
        self._circuit_breaker: CircuitBreaker | None = None
        self._exit_handler_registered = False
```

Add `ILLMClient` to the import line at the top of `lifecycle.py` (line 9):

```python
from ooagent.core.protocols import AgentConfig, HealthStatus, ILifecycle, LifecycleError
```

becomes:

```python
from ooagent.core.protocols import AgentConfig, HealthStatus, ILifecycle, ILLMClient, LifecycleError
```

Replace `health_check` (lines 66-71):

```python
    async def health_check(self) -> HealthStatus:
        if not self._ready:
            return "unhealthy"
        if self._circuit_breaker is not None and self._circuit_breaker.is_open:
            return "degraded"
        return "healthy"
```

with:

```python
    async def health_check(self) -> HealthStatus:
        if not self._ready:
            return "unhealthy"
        if self._llm_client is not None:
            try:
                reachable = await self._llm_client.ping()
            except Exception:
                return "unhealthy"
            if not reachable:
                return "unhealthy"
        if self._circuit_breaker is not None and self._circuit_breaker.is_open:
            return "degraded"
        return "healthy"
```

In `src/ooagent/core/agent.py`, line 120, the `LifecycleManager` construction site:

```python
        self._lifecycle = LifecycleManager(self._plugin_registry, self._state)
```

becomes:

```python
        self._lifecycle = LifecycleManager(self._plugin_registry, self._state, llm_client)
```

- [ ] **Step 4: Run test to verify it passes, and confirm no regressions**

Run: `pytest tests/core/test_lifecycle.py -v`
Expected: all PASS, including the pre-existing `test_initialize_sets_ready_and_health_check_reports_healthy` (its inline `LifecycleManager(PluginRegistry(), SessionState())` has no `llm_client`, so `self._llm_client is None` and the new ping branch is skipped — `health_check()` still returns `"healthy"`).

Run: `pytest tests/core/test_agent.py -v`
Expected: all PASS (`OOAgent`'s `_lifecycle` now carries the real `llm_client`, so `test_llm_failure_increments_circuit_breaker_by_exactly_one`'s two `health_check()` calls must still resolve to `"healthy"` then `"degraded"` — the `_AlwaysFailingLLMClient` from Task 1 has `ping()` returning `True` unconditionally, only `complete()` fails, so this test is unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/lifecycle.py src/ooagent/core/agent.py tests/core/test_lifecycle.py
git commit -m "feat(core): LifecycleManager.health_check() actually pings the LLM client"
```

---

### Task 3: Give `PluginRegistry.verify()` real teeth

**Files:**
- Modify: `src/ooagent/core/registry.py:163-186` (`PluginRegistry`)
- Modify: `src/ooagent/core/protocols.py` (`IPlugin` — add an optional `verify()` hook; see below)
- Test: `tests/core/test_registry.py` (create if it does not already cover `PluginRegistry`)

**Interfaces:**
- Consumes: nothing new from prior tasks in this plan.
- Produces: `PluginRegistry.verify() -> None` — raises `LifecycleError` (already imported/used elsewhere in `core/`) naming the first plugin whose self-check fails. Plugins opt in by overriding a new, non-abstract `IPlugin` method `self_check() -> bool` (default `True` on `AbstractPlugin`, so existing plugins that don't override it are unaffected — this keeps the change additive rather than forcing every existing `IPlugin` implementer to add a method, unlike Task 1's `ping()` which had to be a hard requirement because health probing is `ILLMClient`'s entire job).

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_registry.py` if it doesn't exist, or add to it if it does (check first with a file read):

```python
"""tests/core/test_registry.py — PluginRegistry.verify()."""

from __future__ import annotations

import pytest

from ooagent.core.protocols import IAgent, LifecycleError, PluginContributions
from ooagent.core.registry import PluginRegistry


class _HealthyPlugin:
    plugin_id = "healthy"
    version = "1.0.0"

    def on_register(self, agent: IAgent) -> None:
        return None

    def on_dispose(self) -> None:
        return None

    def contributes(self) -> PluginContributions:
        return PluginContributions()

    def self_check(self) -> bool:
        return True


class _UnhealthyPlugin:
    plugin_id = "unhealthy"
    version = "1.0.0"

    def on_register(self, agent: IAgent) -> None:
        return None

    def on_dispose(self) -> None:
        return None

    def contributes(self) -> PluginContributions:
        return PluginContributions()

    def self_check(self) -> bool:
        return False


def test_verify_passes_when_all_plugins_self_check_true() -> None:
    registry = PluginRegistry()
    registry.register(_HealthyPlugin())
    registry.verify()  # should not raise


def test_verify_raises_lifecycle_error_naming_the_failing_plugin() -> None:
    registry = PluginRegistry()
    registry.register(_HealthyPlugin())
    registry.register(_UnhealthyPlugin())
    with pytest.raises(LifecycleError, match="unhealthy"):
        registry.verify()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_registry.py -v`
Expected: FAIL — `_HealthyPlugin`/`_UnhealthyPlugin` don't structurally satisfy `IPlugin` yet in a way `verify()` can call `self_check()` on (the current `verify()` body is empty, so `test_verify_raises_lifecycle_error_naming_the_failing_plugin` fails because nothing is raised).

- [ ] **Step 3: Implement**

In `src/ooagent/core/protocols.py`, find the `IPlugin` ABC (lines 443-460 per the earlier audit read) and add a concrete (non-abstract) `self_check` default. Since `IPlugin` is an `ABC` with only `@abstractmethod`-decorated members, add `self_check` as a regular (non-abstract) method with a default body:

```python
class IPlugin(ABC):
    @property
    @abstractmethod
    def plugin_id(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    def on_register(self, agent: IAgent[Any, Any]) -> None: ...

    @abstractmethod
    def on_dispose(self) -> None: ...

    @abstractmethod
    def contributes(self) -> PluginContributions: ...

    def self_check(self) -> bool:
        """Health-check hook — PluginRegistry.verify() calls this on every
        registered plugin. Default: always healthy. Override to report real
        readiness (e.g. a cache plugin whose backing store is unreachable)."""
        return True
```

In `src/ooagent/core/registry.py`, replace `PluginRegistry.verify()` (lines 173-174):

```python
    def verify(self) -> None:
        """Health check hook — subclasses add specific checks."""
```

with:

```python
    def verify(self) -> None:
        """Calls IPlugin.self_check() on every registered plugin — §6
        CLAUDE.md LifecycleManager responsibility 2 ("PluginRegistry.verify()")."""
        for plugin in self._plugins.values():
            if not plugin.self_check():
                raise LifecycleError(f"Plugin failed self-check: {plugin.plugin_id}")
```

Add `LifecycleError` to `registry.py`'s imports if not already present (check the existing top-of-file import block from `ooagent.core.protocols` and add `LifecycleError` to it).

- [ ] **Step 4: Run tests to verify they pass, and confirm no regressions**

Run: `pytest tests/core/test_registry.py -v`
Expected: all PASS.

Run: `pytest tests/plugins/ tests/core/test_lifecycle.py -v`
Expected: all PASS — every existing concrete plugin (`AuditPlugin`, `CachePlugin`, `LoggingPlugin`, `OpenTelemetryPlugin`, `RateLimitPlugin`, `ScopeGuardPlugin`, `SecurityPlugin`, `ToolKitPlugin`) inherits the default `self_check() -> True` from `AbstractPlugin`/`IPlugin` and is unaffected. `LifecycleManager.initialize()` (which calls `self._plugin_registry.verify()` at `lifecycle.py:59`) continues to succeed for all of them.

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/protocols.py src/ooagent/core/registry.py tests/core/test_registry.py
git commit -m "feat(core): PluginRegistry.verify() calls IPlugin.self_check() on every plugin"
```

---

### Task 4: Enforce `tool_timeout_ms` around tool execution

**Files:**
- Modify: `src/ooagent/core/agent.py:299-318` (`_execute_tool`)
- Test: `tests/core/test_agent.py`

**Interfaces:**
- Consumes: `self._config.tool_timeout_ms` (already exists on `AgentConfig`, currently unread anywhere in `core/`).
- Produces: `_execute_tool` now raises/handles `TimeoutError` the same way it already handles any other tool exception (returns `{"error": ...}` and fires the existing `tool.call_failed` telemetry event) — no new exception type, no FSM change, no new caller-visible behavior beyond bounding the wait.

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_agent.py`:

```python
async def test_tool_execution_times_out_and_reports_failure_not_hang() -> None:
    import asyncio

    class _SlowTool(BaseTool):
        name = "slow"
        description = "Never returns in time."

        def input_schema(self):
            return {"type": "object", "properties": {}}

        async def execute(self, args):
            await asyncio.sleep(60)
            return {"ok": True}

    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_ToolUseLLMClient("slow"), telemetry=telemetry)
    agent._tool_registry.register(_SlowTool())
    await agent.initialize(AgentConfig(tool_timeout_ms=50))

    artifact = await agent.respond(Query(text="use the slow tool"))

    assert ("tool.call_started", {"tool": "slow"}) in telemetry.events
    failed_events = [e for e in telemetry.events if e[0] == "tool.call_failed" and e[1]["tool"] == "slow"]
    assert len(failed_events) == 1
    assert failed_events[0][1]["error_type"] == "TimeoutError"
    assert artifact is not None

    await agent.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_agent.py::test_tool_execution_times_out_and_reports_failure_not_hang -v --timeout=70`

(Use `pytest-timeout` if installed as a safety net during development; if not installed, be prepared to manually interrupt — the whole point of this failing run is that it currently blocks for the full 60s sleep instead of timing out at 50ms.)

Expected: FAIL — either the test takes ~60 seconds (no timeout enforcement yet) or `error_type` is not `"TimeoutError"`.

- [ ] **Step 3: Implement**

In `src/ooagent/core/agent.py`, replace `_execute_tool` (lines 299-318):

```python
    async def _execute_tool(self, tool_call: ToolCall) -> Any:
        tool = self._tool_registry.get(tool_call.name)
        if tool is None:
            self._telemetry.event(
                "tool.call_failed",
                {"tool": tool_call.name, "error_type": "ToolNotFound"},
            )
            return {"error": f"Tool not found: {tool_call.name}"}
        self._telemetry.event("tool.call_started", {"tool": tool_call.name})
        try:
            result = await tool.execute(tool_call.args)
        except Exception as err:
            _logger.exception("[OOAgent] Tool execution error: %s", tool_call.name)
            self._telemetry.event(
                "tool.call_failed",
                {"tool": tool_call.name, "error_type": type(err).__name__},
            )
            return {"error": str(err)}
        self._telemetry.event("tool.call_completed", {"tool": tool_call.name})
        return result
```

with:

```python
    async def _execute_tool(self, tool_call: ToolCall) -> Any:
        tool = self._tool_registry.get(tool_call.name)
        if tool is None:
            self._telemetry.event(
                "tool.call_failed",
                {"tool": tool_call.name, "error_type": "ToolNotFound"},
            )
            return {"error": f"Tool not found: {tool_call.name}"}
        self._telemetry.event("tool.call_started", {"tool": tool_call.name})
        timeout_s = (self._config.tool_timeout_ms if self._config else 30_000) / 1000
        try:
            result = await asyncio.wait_for(tool.execute(tool_call.args), timeout=timeout_s)
        except Exception as err:
            _logger.exception("[OOAgent] Tool execution error: %s", tool_call.name)
            self._telemetry.event(
                "tool.call_failed",
                {"tool": tool_call.name, "error_type": type(err).__name__},
            )
            return {"error": str(err)}
        self._telemetry.event("tool.call_completed", {"tool": tool_call.name})
        return result
```

Add `import asyncio` to the top of `agent.py`'s import block (it currently imports `json`, `logging`, `time`, `uuid` at lines 5-8 — add `asyncio` alongside them, keeping alphabetical order per the `ruff` `I` (isort) rule: `asyncio` sorts before `json`).

Note: `asyncio.wait_for` raises `asyncio.TimeoutError`, which in Python 3.11 is an alias for the builtin `TimeoutError` (they were unified in 3.11) — `type(err).__name__` will report `"TimeoutError"`, matching the test's assertion.

- [ ] **Step 4: Run test to verify it passes (fast this time)**

Run: `pytest tests/core/test_agent.py::test_tool_execution_times_out_and_reports_failure_not_hang -v`
Expected: PASS, completing in ~50-200ms, not 60 seconds.

Run: `pytest tests/core/test_agent.py -v`
Expected: all PASS — existing tool-call tests (`test_tool_call_events_fire_on_success`, etc.) use fast synchronous stub tools well under the default 30s `tool_timeout_ms`, unaffected.

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/agent.py tests/core/test_agent.py
git commit -m "fix(core): enforce tool_timeout_ms around tool execution"
```

---

### Task 5: Enforce `turn_timeout_ms` around the LLM completion call

**Files:**
- Modify: `src/ooagent/core/agent.py:244-268` (`_llm_tool_loop`, the `self._llm_client.complete(request)` call site)
- Test: `tests/core/test_agent.py`

**Interfaces:**
- Consumes: `self._config.turn_timeout_ms` (already exists on `AgentConfig`).
- Produces: the LLM `complete()` call is bounded; a timeout is treated identically to any other LLM-call exception (fires `llm.call_failed`, calls `self._lifecycle.record_llm_failure()`, re-raises so `_solve`'s caller in `respond()`'s `try/except` around `SOLVING` catches it and routes to `_handle_failure`, exactly as `_AlwaysFailingLLMClient` already does in the existing test suite).

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_agent.py`:

```python
async def test_llm_call_times_out_and_is_handled_as_a_failure() -> None:
    import asyncio

    class _SlowLLMClient(ILLMClient):
        async def complete(self, request):
            await asyncio.sleep(60)
            return CompletionResponse(
                content="too slow", stop_reason="end_turn", usage=TokenUsage(input_tokens=1, output_tokens=1)
            )

        async def ping(self) -> bool:
            return True

        async def stream(self, request):
            yield CompletionChunk(delta="", done=True)

        @property
        def model_id(self):
            return "slow-1"

        @property
        def vendor(self):
            return "anthropic"

        @property
        def max_tokens(self):
            return 4096

        @property
        def supports_tools(self):
            return False

    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_SlowLLMClient(), telemetry=telemetry)
    await agent.initialize(AgentConfig(turn_timeout_ms=50))

    artifact = await agent.respond(Query(text="hello agent"))

    failed_events = [e for e in telemetry.events if e[0] == "llm.call_failed"]
    assert len(failed_events) == 1
    assert failed_events[0][1]["error_type"] == "TimeoutError"
    assert artifact is not None
    assert agent.state.fsm == "IDLE"

    await agent.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_agent.py::test_llm_call_times_out_and_is_handled_as_a_failure -v --timeout=70`
Expected: FAIL — hangs for ~60s (no timeout enforcement yet).

- [ ] **Step 3: Implement**

In `src/ooagent/core/agent.py`, in `_llm_tool_loop`, replace lines 255-256:

```python
            try:
                response = await self._llm_client.complete(request)
                self._lifecycle.record_llm_success()
```

with:

```python
            timeout_s = (config.turn_timeout_ms if config else 60_000) / 1000
            try:
                response = await asyncio.wait_for(self._llm_client.complete(request), timeout=timeout_s)
                self._lifecycle.record_llm_success()
```

(`config` is already bound at the top of `_llm_tool_loop`, line 234: `config = self._config` — reuse it rather than re-reading `self._config`.)

- [ ] **Step 4: Run test to verify it passes (fast), and confirm no regressions**

Run: `pytest tests/core/test_agent.py::test_llm_call_times_out_and_is_handled_as_a_failure -v`
Expected: PASS, completing in ~50-200ms.

Run: `pytest tests/core/test_agent.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/agent.py tests/core/test_agent.py
git commit -m "fix(core): enforce turn_timeout_ms around the LLM completion call"
```

---

### Task 6: Full-suite regression check and static analysis

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all PASS.

- [ ] **Step 2: Run mypy --strict**

Run: `mypy --strict src/ooagent`
Expected: no errors. Pay attention to `asyncio.wait_for`'s generic return type inference at both new call sites, and to every `ILLMClient` implementer now needing a `ping()` method with a matching `async def ping(self) -> bool` signature.

- [ ] **Step 3: Run ruff**

Run: `ruff check src/ooagent tests`
Expected: no errors — in particular confirm the new `import asyncio` in `agent.py` is correctly sorted per the `I` (isort) rule.

- [ ] **Step 4: Commit if any lint-only fixups were needed**

```bash
git add -A
git commit -m "chore: lint/type fixups for lifecycle health and timeout work"
```

(Skip this commit entirely if steps 1-3 were already clean.)

---

## Closing notes (explicitly out of scope for this plan)

- `ping()` returns `True` unconditionally on every real vendor adapter in this pass — it does not perform a live network round-trip against Anthropic/OpenAI/Gemini/Ollama. Wiring a real lightweight health-check request per vendor (e.g. a minimal `models.list` or equivalent) is meaningful follow-up work but requires live credentials to verify in CI/locally, which this environment does not have. The gap this plan closes is structural: the interface exists, the call site exists, and `health_check()` actually calls it — a future task can swap the trivial `True` body for a real probe per adapter without touching `LifecycleManager` or `agent.py` again.
- `specialist_timeout_ms` and `orchestration_timeout_ms` remain unused — they belong to `IOrchestrator`/`MultiAgentOrchestrator` (CLAUDE.md §13), which this plan's fact-gathering did not find implemented anywhere in `src/ooagent/core/orchestrator.py` in enough detail to safely wire a timeout into in this pass. Confirm the current state of `orchestrator.py` before starting follow-up work here.
