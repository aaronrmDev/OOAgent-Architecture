# Observability & Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Instrument the currently-silent failure/tool/LLM-call paths in `core/agent.py` with four new additive telemetry events, prove each fires with the correct payload, and document the resulting event schema plus the already-built `DefaultSecurityPolicy` redaction/policy story in a new `docs/OBSERVABILITY.md`.

**Architecture:** Every change to `src/ooagent/core/agent.py` is a pure, side-effect-only insertion of `self._telemetry.event(name, payload)` calls — no control flow, exception type, return value, or FSM transition changes anywhere in the file. Tests use a new `_RecordingTelemetry(ITelemetryProvider)` test double (appends `(name, payload)` tuples to a list) added to `tests/core/test_agent.py`, exercising the new events via `OOAgent(llm_client=..., telemetry=_RecordingTelemetry())`.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio (existing project conventions — no new dependencies).

## Global Constraints

- `core/agent.py`'s control flow, exception types, return values, and FSM transitions must be byte-for-byte unchanged except for the four additive `self._telemetry.event(...)` call sites — this is the composition root and the highest-risk file in the codebase (CLAUDE.md §10's frozen Template Method).
- `ITelemetryProvider.event(name: str, payload: dict[str, Any]) -> None` is synchronous (not `async def`) — never `await` it.
- Event schema (exact names and payload keys, from the design spec `docs/superpowers/specs/2026-07-08-observability-safety-design.md`):
  - `llm.call_started` `{round: int, vendor: LLMVendor}`
  - `llm.call_completed` `{round: int, vendor: LLMVendor, input_tokens: int, output_tokens: int}`
  - `llm.call_failed` `{round: int, vendor: LLMVendor, error_type: str}`
  - `tool.call_started` `{tool: str}`
  - `tool.call_completed` `{tool: str}`
  - `tool.call_failed` `{tool: str, error_type: str}` — `error_type == "ToolNotFound"` for unregistered tools
  - `turn.failed` `{context: str, error_type: str, recoverable: bool}` — `recoverable=True` from `_handle_failure`, `recoverable=False` from `_handle_unrecoverable_failure`
- `error_type` is always `type(err).__name__`.
- No edits to `core/pipeline.py`, `core/state.py`, `core/lifecycle.py`, or any plugin — out of scope per the design spec.
- No new spans per FSM phase, no changes to `DefaultSecurityPolicy`/`ScopeGuardPlugin`, no changes to `examples/telemetry_enabled_agent.py`, no correlation/session IDs — all explicitly out of scope per the design spec.
- With no domain context registered (the state every test in `tests/core/test_agent.py` runs in, via the `_reset_context_registry_singleton` autouse fixture), `ContextRegistry.resolve()` always returns a context whose `.name` is the literal string `"NullContext"`.

---

## File Structure

- Modify `src/ooagent/core/agent.py` — four additive telemetry call sites (Tasks 1-4).
- Modify `tests/core/test_agent.py` — new `_RecordingTelemetry` double, new `_ToolUseLLMClient` double, new `_EchoTool`/`_RaisingTool` stub tools, eight new tests (Tasks 1-4).
- Create `docs/OBSERVABILITY.md` — event schema, failure taxonomy, wiring guide, policy-hooks pointer, safe defaults (Task 5).
- Modify `README.md` — one new "Go Deeper" line pointing at `docs/OBSERVABILITY.md` (Task 5).

---

### Task 1: LLM call events in `_llm_tool_loop`

**Files:**
- Modify: `src/ooagent/core/agent.py:252-257`
- Test: `tests/core/test_agent.py`

**Interfaces:**
- Consumes: `ITelemetryProvider.event(name: str, payload: dict[str, Any]) -> None` (existing, `core/protocols.py`); `CompletionResponse.usage: TokenUsage` with `.input_tokens: int`/`.output_tokens: int` (existing); `ILLMClient.vendor: LLMVendor` (existing property).
- Produces: `_RecordingTelemetry` class in `tests/core/test_agent.py`, reused by Tasks 2-4. Shape:
  ```python
  class _RecordingTelemetry(ITelemetryProvider):
      def __init__(self) -> None:
          self.events: list[tuple[str, dict]] = []

      async def span(self, name, fn):
          return await fn()

      def counter(self, name, delta=1):
          return None

      def gauge(self, name, value):
          return None

      def histogram(self, name, value):
          return None

      def event(self, name, payload):
          self.events.append((name, payload))
  ```

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/test_agent.py`, after the existing `import` block (after line 17, before `class _StubLLMClient`), add `ITelemetryProvider` to the existing import from `ooagent.core.protocols`:

```python
from ooagent.core.protocols import (
    AgentConfig,
    CompletionChunk,
    CompletionResponse,
    ILLMClient,
    ITelemetryProvider,
    LifecycleError,
    Query,
    TokenUsage,
)
```

Then, after the `_AlwaysFailingLLMClient` class (after line 135, before `test_llm_failure_increments_circuit_breaker_by_exactly_one`), add:

```python
class _RecordingTelemetry(ITelemetryProvider):
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def span(self, name, fn):
        return await fn()

    def counter(self, name, delta=1):
        return None

    def gauge(self, name, value):
        return None

    def histogram(self, name, value):
        return None

    def event(self, name, payload):
        self.events.append((name, payload))


async def test_llm_call_events_fire_on_success() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_StubLLMClient(), telemetry=telemetry)
    await agent.initialize(AgentConfig())

    await agent.respond(Query(text="hello agent"))

    assert ("llm.call_started", {"round": 0, "vendor": "anthropic"}) in telemetry.events
    assert (
        "llm.call_completed",
        {"round": 0, "vendor": "anthropic", "input_tokens": 1, "output_tokens": 1},
    ) in telemetry.events

    await agent.dispose()


async def test_llm_call_failed_event_fires_on_llm_error() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_AlwaysFailingLLMClient(), telemetry=telemetry)
    await agent.initialize(AgentConfig())

    await agent.respond(Query(text="hello agent"))

    assert ("llm.call_started", {"round": 0, "vendor": "anthropic"}) in telemetry.events
    assert (
        "llm.call_failed",
        {"round": 0, "vendor": "anthropic", "error_type": "RuntimeError"},
    ) in telemetry.events

    await agent.dispose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_agent.py::test_llm_call_events_fire_on_success tests/core/test_agent.py::test_llm_call_failed_event_fires_on_llm_error -v`
Expected: both FAIL (`AssertionError`, since `telemetry.events` is empty — no `llm.call_*` events exist yet).

- [ ] **Step 3: Instrument `_llm_tool_loop`'s LLM call**

In `src/ooagent/core/agent.py`, replace the LLM-call block at lines 252-257:

Before:
```python
            try:
                response = await self._llm_client.complete(request)
                self._lifecycle.record_llm_success()
            except Exception:
                self._lifecycle.record_llm_failure()
                raise
```

After:
```python
            self._telemetry.event(
                "llm.call_started", {"round": _round, "vendor": self._llm_client.vendor}
            )
            try:
                response = await self._llm_client.complete(request)
                self._lifecycle.record_llm_success()
            except Exception as err:
                self._lifecycle.record_llm_failure()
                self._telemetry.event(
                    "llm.call_failed",
                    {
                        "round": _round,
                        "vendor": self._llm_client.vendor,
                        "error_type": type(err).__name__,
                    },
                )
                raise
            self._telemetry.event(
                "llm.call_completed",
                {
                    "round": _round,
                    "vendor": self._llm_client.vendor,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )
```

Nothing else in the method changes — `_round` is the existing `for _round in range(max_rounds):` loop variable already in scope (line 244).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_agent.py -v`
Expected: all tests in the file PASS, including the two new ones (10 tests total).

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/agent.py tests/core/test_agent.py
git commit -m "feat(observability): emit llm.call_started/completed/failed telemetry events"
```

---

### Task 2: Tool call events in `_execute_tool`

**Files:**
- Modify: `src/ooagent/core/agent.py:279-287`
- Test: `tests/core/test_agent.py`

**Interfaces:**
- Consumes: `_RecordingTelemetry` (Task 1); `BaseTool` (`ooagent.adapters.tools.base`, existing — `name`/`description`/`input_schema()`/`execute()` abstract, `to_vendor_spec()` provided); `ToolCall(id: str, name: str, args: dict[str, Any])` (existing, `core/protocols.py`).
- Produces: `_ToolUseLLMClient`, `_EchoTool`, `_RaisingTool` classes in `tests/core/test_agent.py`, available for reuse by any later task that needs a tool-calling round (none in this plan, but kept discoverable).

- [ ] **Step 1: Write the failing tests**

Add `ToolCall` to the existing `ooagent.core.protocols` import in `tests/core/test_agent.py` (from Task 1's edit):

```python
from ooagent.core.protocols import (
    AgentConfig,
    CompletionChunk,
    CompletionResponse,
    ILLMClient,
    ITelemetryProvider,
    LifecycleError,
    Query,
    TokenUsage,
    ToolCall,
)
```

Add a new top-level import for `BaseTool`, immediately after the `ooagent.core.registry` import (after line 17):

```python
from ooagent.adapters.tools.base import BaseTool
```

Add these classes after `_RecordingTelemetry` (added in Task 1) and before `test_llm_call_events_fire_on_success`:

```python
class _ToolUseLLMClient(ILLMClient):
    """Returns one tool_use round for `tool_name`, then end_turn."""

    def __init__(self, tool_name: str) -> None:
        self._tool_name = tool_name
        self._calls = 0

    async def complete(self, request):
        self._calls += 1
        if self._calls == 1:
            return CompletionResponse(
                content="",
                stop_reason="tool_use",
                usage=TokenUsage(input_tokens=1, output_tokens=1),
                tool_calls=[ToolCall(id="call-1", name=self._tool_name, args={"text": "hi"})],
            )
        return CompletionResponse(
            content="done",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    async def stream(self, request):
        yield CompletionChunk(delta="", done=True)

    @property
    def model_id(self):
        return "stub-tool-use"

    @property
    def vendor(self):
        return "anthropic"

    @property
    def max_tokens(self):
        return 4096

    @property
    def supports_tools(self):
        return True


class _EchoTool(BaseTool):
    name = "echo"
    description = "Echoes input text."

    def input_schema(self):
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    async def execute(self, args):
        return {"echo": args["text"]}


class _RaisingTool(BaseTool):
    name = "raiser"
    description = "Always raises."

    def input_schema(self):
        return {"type": "object", "properties": {}}

    async def execute(self, args):
        raise ValueError("tool exploded")
```

Then add the three new tests, after `test_llm_call_failed_event_fires_on_llm_error` (added in Task 1):

```python
async def test_tool_call_events_fire_on_success() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_ToolUseLLMClient("echo"), telemetry=telemetry)
    agent._tool_registry.register(_EchoTool())
    await agent.initialize(AgentConfig())

    await agent.respond(Query(text="use the echo tool"))

    assert ("tool.call_started", {"tool": "echo"}) in telemetry.events
    assert ("tool.call_completed", {"tool": "echo"}) in telemetry.events
    started_idx = telemetry.events.index(("tool.call_started", {"tool": "echo"}))
    completed_idx = telemetry.events.index(("tool.call_completed", {"tool": "echo"}))
    assert started_idx < completed_idx

    await agent.dispose()


async def test_tool_call_failed_event_fires_when_tool_raises() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_ToolUseLLMClient("raiser"), telemetry=telemetry)
    agent._tool_registry.register(_RaisingTool())
    await agent.initialize(AgentConfig())

    await agent.respond(Query(text="use the raiser tool"))

    assert ("tool.call_started", {"tool": "raiser"}) in telemetry.events
    assert (
        "tool.call_failed",
        {"tool": "raiser", "error_type": "ValueError"},
    ) in telemetry.events

    await agent.dispose()


async def test_tool_call_failed_event_fires_when_tool_not_found() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_ToolUseLLMClient("missing"), telemetry=telemetry)
    await agent.initialize(AgentConfig())

    await agent.respond(Query(text="use a missing tool"))

    assert (
        "tool.call_failed",
        {"tool": "missing", "error_type": "ToolNotFound"},
    ) in telemetry.events
    assert ("tool.call_started", {"tool": "missing"}) not in telemetry.events

    await agent.dispose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_agent.py::test_tool_call_events_fire_on_success tests/core/test_agent.py::test_tool_call_failed_event_fires_when_tool_raises tests/core/test_agent.py::test_tool_call_failed_event_fires_when_tool_not_found -v`
Expected: all three FAIL (`AssertionError` — no `tool.call_*` events exist yet).

- [ ] **Step 3: Instrument `_execute_tool`**

In `src/ooagent/core/agent.py`, replace lines 279-287:

Before:
```python
    async def _execute_tool(self, tool_call: ToolCall) -> Any:
        tool = self._tool_registry.get(tool_call.name)
        if tool is None:
            return {"error": f"Tool not found: {tool_call.name}"}
        try:
            return await tool.execute(tool_call.args)
        except Exception as err:
            _logger.exception("[OOAgent] Tool execution error: %s", tool_call.name)
            return {"error": str(err)}
```

After:
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_agent.py -v`
Expected: all tests PASS (13 tests total).

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/agent.py tests/core/test_agent.py
git commit -m "feat(observability): emit tool.call_started/completed/failed telemetry events"
```

---

### Task 3: `turn.failed` (recoverable=True) in `_handle_failure`

**Files:**
- Modify: `src/ooagent/core/agent.py:289-301`
- Test: `tests/core/test_agent.py`

**Interfaces:**
- Consumes: `_RecordingTelemetry` (Task 1), `_AlwaysFailingLLMClient` (existing, line 114).
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Write the failing test**

Add, after `test_tool_call_failed_event_fires_when_tool_not_found` (Task 2):

```python
async def test_turn_failed_event_fires_recoverable_true_on_llm_failure() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_AlwaysFailingLLMClient(), telemetry=telemetry)
    await agent.initialize(AgentConfig())

    await agent.respond(Query(text="hello agent"))

    assert (
        "turn.failed",
        {"context": "NullContext", "error_type": "RuntimeError", "recoverable": True},
    ) in telemetry.events

    await agent.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_agent.py::test_turn_failed_event_fires_recoverable_true_on_llm_failure -v`
Expected: FAIL (`AssertionError` — no `turn.failed` event exists yet).

- [ ] **Step 3: Instrument `_handle_failure`**

In `src/ooagent/core/agent.py`, replace lines 289-301:

Before:
```python
    def _handle_failure(
        self, err: Exception, context: IDomainContext, _snapshot_id: str
    ) -> Artifact:
        self._state.transition("FAILURE")
        if isinstance(err, ScopeExitError):
            artifact = self._artifact_factory.build_scope_exit(context.name, err.query)
        elif isinstance(err, ConstraintViolationError):
            artifact = self._artifact_factory.build_error(str(err), context.name)
        else:
            artifact = self._artifact_factory.build_error(str(err), context.name)
        self._state.transition("DELIVERING")
        self._state.reset()
        return artifact
```

After:
```python
    def _handle_failure(
        self, err: Exception, context: IDomainContext, _snapshot_id: str
    ) -> Artifact:
        self._state.transition("FAILURE")
        self._telemetry.event(
            "turn.failed",
            {"context": context.name, "error_type": type(err).__name__, "recoverable": True},
        )
        if isinstance(err, ScopeExitError):
            artifact = self._artifact_factory.build_scope_exit(context.name, err.query)
        elif isinstance(err, ConstraintViolationError):
            artifact = self._artifact_factory.build_error(str(err), context.name)
        else:
            artifact = self._artifact_factory.build_error(str(err), context.name)
        self._state.transition("DELIVERING")
        self._state.reset()
        return artifact
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_agent.py -v`
Expected: all tests PASS (14 tests total).

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/agent.py tests/core/test_agent.py
git commit -m "feat(observability): emit turn.failed (recoverable=true) from _handle_failure"
```

---

### Task 4: `turn.failed` (recoverable=False) in `_handle_unrecoverable_failure`

**Files:**
- Modify: `src/ooagent/core/agent.py:303-323`
- Test: `tests/core/test_agent.py`

**Interfaces:**
- Consumes: `_RecordingTelemetry` (Task 1), `_StubLLMClient` (existing, line 20), the `_boom` decorator pattern already used in `test_respond_recovers_when_artifact_factory_raises_during_delivering` (existing, line 88).
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Write the failing test**

Add, after `test_turn_failed_event_fires_recoverable_true_on_llm_failure` (Task 3):

```python
async def test_turn_failed_event_fires_recoverable_false_on_delivering_failure() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_StubLLMClient(), telemetry=telemetry)
    await agent.initialize(AgentConfig())

    def _boom(artifact, provenance):
        raise RuntimeError("boom")

    agent._decorator.add_decorator(_boom)

    await agent.respond(Query(text="hello agent"))

    assert (
        "turn.failed",
        {"context": "NullContext", "error_type": "RuntimeError", "recoverable": False},
    ) in telemetry.events

    await agent.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_agent.py::test_turn_failed_event_fires_recoverable_false_on_delivering_failure -v`
Expected: FAIL (`AssertionError` — no `turn.failed` event with `recoverable: False` exists yet).

- [ ] **Step 3: Instrument `_handle_unrecoverable_failure`**

In `src/ooagent/core/agent.py`, replace lines 303-323:

Before:
```python
    def _handle_unrecoverable_failure(
        self, err: Exception, context: IDomainContext | None
    ) -> Artifact:
        """Recovers from two distinct problems `_handle_failure` can't handle:
        (1) a failure during the context-resolution prelude, where `context`
        itself may not be bound yet — there's no object to pass to
        `_handle_failure(err, context, ...)`, which requires one; and (2) a
        failure in the DELIVERING block, where `_handle_failure`'s
        `transition("FAILURE")` would itself be illegal, since
        `VALID_TRANSITIONS["DELIVERING"] = {"IDLE"}` in state.py is the only
        legal exit from DELIVERING. `reset()` force-assigns `_fsm = IDLE`
        unconditionally, bypassing the transition-legality check, which is
        the only way to safely recover from either case."""
        context_name = context.name if context is not None else "unknown"
        if isinstance(err, ScopeExitError):
            artifact = self._artifact_factory.build_scope_exit(context_name, err.query)
        else:
            artifact = self._artifact_factory.build_error(str(err), context_name)
        self._state.reset()
        self._lifecycle.record_llm_failure()
        return artifact
```

After:
```python
    def _handle_unrecoverable_failure(
        self, err: Exception, context: IDomainContext | None
    ) -> Artifact:
        """Recovers from two distinct problems `_handle_failure` can't handle:
        (1) a failure during the context-resolution prelude, where `context`
        itself may not be bound yet — there's no object to pass to
        `_handle_failure(err, context, ...)`, which requires one; and (2) a
        failure in the DELIVERING block, where `_handle_failure`'s
        `transition("FAILURE")` would itself be illegal, since
        `VALID_TRANSITIONS["DELIVERING"] = {"IDLE"}` in state.py is the only
        legal exit from DELIVERING. `reset()` force-assigns `_fsm = IDLE`
        unconditionally, bypassing the transition-legality check, which is
        the only way to safely recover from either case."""
        context_name = context.name if context is not None else "unknown"
        self._telemetry.event(
            "turn.failed",
            {"context": context_name, "error_type": type(err).__name__, "recoverable": False},
        )
        if isinstance(err, ScopeExitError):
            artifact = self._artifact_factory.build_scope_exit(context_name, err.query)
        else:
            artifact = self._artifact_factory.build_error(str(err), context_name)
        self._state.reset()
        self._lifecycle.record_llm_failure()
        return artifact
```

The docstring is preserved verbatim — only the `self._telemetry.event(...)` call is inserted, immediately after `context_name` is computed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_agent.py -v`
Expected: all tests PASS (15 tests total).

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/agent.py tests/core/test_agent.py
git commit -m "feat(observability): emit turn.failed (recoverable=false) from _handle_unrecoverable_failure"
```

---

### Task 5: `docs/OBSERVABILITY.md` and README link

**Files:**
- Create: `docs/OBSERVABILITY.md`
- Modify: `README.md:54-61`

**Interfaces:**
- Consumes: the finished event schema from Tasks 1-4 (no code interfaces — this is a docs-only task).
- Produces: nothing consumed by other tasks (final task in this plan).

- [ ] **Step 1: Write `docs/OBSERVABILITY.md`**

Create `docs/OBSERVABILITY.md`:

```markdown
# Observability & Safety

`OOAgent` emits structured telemetry events through the injected
`ITelemetryProvider` at every LLM call, tool call, and turn-level failure.
Wire a real provider (`ConsoleTelemetry` for development,
`OpenTelemetryProvider` for production) to see them; the default
`NullTelemetry` is a no-op, per CLAUDE.md's Null Object pattern.

## Event schema

One `agent.turn` span wraps every `respond()` call (existing). Within it:

| Event | Payload | Fires when |
|---|---|---|
| `llm.call_started` | `{round: int, vendor: LLMVendor}` | before each LLM completion request |
| `llm.call_completed` | `{round: int, vendor: LLMVendor, input_tokens: int, output_tokens: int}` | the LLM call returns successfully |
| `llm.call_failed` | `{round: int, vendor: LLMVendor, error_type: str}` | the LLM call raises |
| `tool.call_started` | `{tool: str}` | before a resolved tool's `execute()` runs |
| `tool.call_completed` | `{tool: str}` | the tool call returns successfully |
| `tool.call_failed` | `{tool: str, error_type: str}` | the tool call raises, or the tool name isn't registered (`error_type: "ToolNotFound"`) |
| `turn.failed` | `{context: str, error_type: str, recoverable: bool}` | any turn ends in `FAILURE` |
| `turn.complete` | `{context: str, format: str, turn: int}` | a turn completes successfully (existing) |

`round` is 0-indexed per `respond()` call. `error_type` is always
`type(err).__name__`.

## Failure taxonomy

`turn.failed`'s `error_type` and `recoverable` fields map onto
`core/protocols.py`'s exception hierarchy and CLAUDE.md §16's failure modes:

| Exception | Raised by | `recoverable` | CLAUDE.md §16 response |
|---|---|---|---|
| `ConstraintViolationError` | `ConstraintEngine.assert_all()` in VALIDATING, or a pipeline step in MODELING | `True` | Halt, emit violation report, reset FSM to IDLE |
| `ScopeExitError` | domain context's pipeline / `_solve()` in SOLVING | `True` | Declare scope exit, list contexts that would satisfy the query |
| `FSMViolationError` | `SessionState.transition()` on an illegal transition | `True` or `False` (whichever handler catches it) | Always a programming error — reset to IDLE, log full FSM trace |
| `ToolExecutionError` | a tool's `execute()` (surfaces as a tool result, not a turn failure — see `tool.call_failed` instead) | n/a | Continue the turn without the tool result |
| `TokenLimitError` | an `ILLMClient` adapter, when a request exceeds the model's context window | `True` | Truncate/report per adapter; the turn ends via `_handle_failure` |
| `LifecycleError` | `respond()` called before `initialize()`, or after `dispose()` | raised before any FSM transition — no `turn.failed` event | Caller error — fix the call site |
| Any other exception (e.g. a bare `RuntimeError` from an `ILLMClient`, or a third-party `ResponseDecorator`) | provider/plugin code | `True` in MODELING/SOLVING/VALIDATING, `False` in the GATHERING prelude or DELIVERING | Emit degraded response, log via telemetry |

`recoverable=True` means `_handle_failure` caught it (MODELING, SOLVING, or
VALIDATING); `recoverable=False` means `_handle_unrecoverable_failure` caught
it (the GATHERING prelude, before a context is resolved, or DELIVERING,
after `ConstraintEngine.assert_all()` already passed). Both paths always
leave the FSM in `IDLE` before `respond()` returns.

## Wiring a real telemetry backend

```python
from ooagent.telemetry.console import ConsoleTelemetry
from ooagent.core.agent import OOAgent

agent = OOAgent(llm_client=my_client, telemetry=ConsoleTelemetry())
```

Swap `ConsoleTelemetry()` for `OpenTelemetryProvider(...)` in production —
see `examples/telemetry_enabled_agent.py` for a runnable end-to-end example
of both. No other code changes; `ITelemetryProvider` is the only interface
`OOAgent` depends on (DIP, CLAUDE.md §2).

## Policy hooks and redaction (already built)

`DefaultSecurityPolicy` (`src/ooagent/plugins/security/policy_engine.py`)
already covers most of what "policy hooks" and "redaction strategy" mean in
practice:

- **Prompt-injection detection** — pattern-based scanning of inbound query
  text.
- **PII redaction** — pattern-based redaction of common PII shapes before
  content is logged or persisted.
- **Rate limiting** — per-caller request throttling.
- **Access control** — allow/deny checks before a turn proceeds.
- **Output validation** — pattern-based scanning of outbound artifact
  content.

Wire it via `SecureToolWrapper` (`plugins/security/secure_tool_wrapper.py`,
wraps an `ITool` to run policy checks around `execute()`) or by registering
a `SecurityPlugin` contribution — see `plugins/security/` for both. Neither
is modified by this document; this section exists so the capability is
discoverable.

## Safe defaults

`AgentConfig` (`core/protocols.py`) ships these defaults unchanged by this
document:

- `max_tool_rounds` — bounds the LLM/tool loop; the loop emits
  `[TokenBudgetExceeded]` and returns a truncated `Solution` if exceeded.
- `circuit_breaker_threshold` — consecutive LLM failures (tracked via
  `record_llm_failure()`/`record_llm_success()`) before `LifecycleManager`
  reports `"degraded"` from `health_check()`.
- Retry/backoff and per-turn timeout budgets — see `core/lifecycle.py` for
  the current values; this document does not change them.
```

- [ ] **Step 2: Link from README**

In `README.md`, modify the "Go Deeper" list at lines 54-61:

Before:
```markdown
## Go Deeper

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — composition root, design patterns, project structure, extension protocol
- [`docs/PUBLIC_API.md`](docs/PUBLIC_API.md) — what's core vs. advanced, and the stability contract
- [`docs/TESTING.md`](docs/TESTING.md) — how to test adapters without network calls, test doubles, coverage floor
- [`CLAUDE.md`](CLAUDE.md) — the full architectural contract: invariants, FSM, failure modes, testing contracts
- [`CONTRIBUTORS.md`](CONTRIBUTORS.md) — how to contribute
```

After:
```markdown
## Go Deeper

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — composition root, design patterns, project structure, extension protocol
- [`docs/PUBLIC_API.md`](docs/PUBLIC_API.md) — what's core vs. advanced, and the stability contract
- [`docs/TESTING.md`](docs/TESTING.md) — how to test adapters without network calls, test doubles, coverage floor
- [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md) — event schema, failure taxonomy, wiring a telemetry backend, policy hooks and redaction
- [`CLAUDE.md`](CLAUDE.md) — the full architectural contract: invariants, FSM, failure modes, testing contracts
- [`CONTRIBUTORS.md`](CONTRIBUTORS.md) — how to contribute
```

- [ ] **Step 3: Verify the full suite still passes**

Run: `pytest -q`
Expected: PASS, 0 failures (docs-only change plus the four prior tasks' additions — no new test in this task, since there is no code to test).

- [ ] **Step 4: Commit**

```bash
git add docs/OBSERVABILITY.md README.md
git commit -m "docs: add docs/OBSERVABILITY.md (event schema, failure taxonomy, policy hooks pointer)"
```

---

## Self-Review

**Spec coverage:**
- 4 telemetry call sites (`_handle_failure`, `_handle_unrecoverable_failure`, `_execute_tool`, `_llm_tool_loop`'s LLM call) — Tasks 1-4. ✅
- New event names with exact payload shapes — Tasks 1-4's diffs match the design spec's schema verbatim. ✅
- Tests proving each event fires with correct payload, via a new `_RecordingTelemetry` double, reusing existing `_AlwaysFailingLLMClient`/`_boom`-decorator fixtures — Tasks 1, 3, 4 reuse; Task 2 adds `_ToolUseLLMClient` + stub tools as the design spec anticipated. ✅
- `docs/OBSERVABILITY.md` with event schema, failure taxonomy, wiring section, policy-hooks pointer, safe defaults, linked from README — Task 5. ✅
- Out-of-scope items (FSM-phase spans, `DefaultSecurityPolicy`/plugin changes, `examples/telemetry_enabled_agent.py` changes, correlation IDs) — none touched by any task. ✅

**Placeholder scan:** no "TBD"/"TODO"/"add error handling"-style steps; every step has complete code.

**Type consistency:** `_RecordingTelemetry` (Task 1) is reused identically by Tasks 2-4 with no signature drift. `_ToolUseLLMClient(tool_name: str)` (Task 2) is self-contained to that task. Payload dict keys and value types match the Global Constraints schema exactly across all four instrumented sites.
