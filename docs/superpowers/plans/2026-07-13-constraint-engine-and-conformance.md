# Constraint Engine Enforcement & IAgent Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ConstraintEngine` capable of actually raising on invariant failure (it is currently a permanent no-op), wire an injectable instance into `OOAgent`, fix the one illegal-FSM-shortcut that has a legal alternative, and replace the 4 skipped `IAgent` conformance stubs in `tests/conformance/test_agent.py` with real assertions.

**Architecture:** `Invariant` (a frozen dataclass in `core/protocols.py`) gains an optional `check: Callable[[Solution], bool] | None` field. `ConstraintEngine._assert` calls it when present and raises `ConstraintViolationError` for `severity == "error"` failures — additive, backward compatible (existing invariants with `check=None` keep passing, exactly as before). `OOAgent.__init__` gains an injectable `constraint_engine` parameter (matching the DIP pattern already used for every other collaborator). A new generic `empty_query_step` pipeline step (base-level, not domain-specific, per CLAUDE.md §11 "Generic invariants (always on, regardless of active context)") is wired as `OOAgent`'s default base pipeline step, giving the `respond(emptyQuery)` conformance test something real to assert against. Separately, `_handle_failure`'s `context` parameter becomes `IDomainContext | None`, letting the GATHERING-prelude except-block route through the legal `GATHERING → FAILURE → DELIVERING → IDLE` path instead of the FSM-bypassing `_handle_unrecoverable_failure`.

**Tech Stack:** Python 3.11, pytest + pytest-asyncio (`asyncio_mode = "auto"`), mypy --strict, ruff.

## Global Constraints

- `mypy --strict` must pass on every file touched (this repo enforces it in CI on `src/ooagent`).
- `ruff` (`select = ["E", "F", "I", "UP", "B"]`, line-length 100) must pass.
- No new runtime dependencies — stdlib only for these changes.
- `core/protocols.py` changes must be additive only (new optional field with a default) — CLAUDE.md §18 requires a major version bump for breaking interface changes; this plan does not bump the version, so it must stay additive.
- Existing tests in `tests/core/test_agent.py`, `tests/core/test_pipeline.py`, `tests/core/test_state.py` must continue to pass unmodified except where a task explicitly changes them.

---

### Task 1: Add an optional `check` callable to `Invariant`

**Files:**
- Modify: `src/ooagent/core/protocols.py:47-52` (the `Invariant` dataclass)
- Test: `tests/core/test_protocols.py`

**Interfaces:**
- Produces: `Invariant(name: str, condition: str, severity: Literal["error", "warning"], rationale: str, check: Callable[[Solution], bool] | None = None)` — the new `check` field, used by Task 2.

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_protocols.py` (create the file if it does not already define this test; if the file exists, append this test function):

```python
def test_invariant_check_field_defaults_to_none_and_accepts_a_callable() -> None:
    from ooagent.core.protocols import Invariant, Solution

    bare = Invariant(name="n", condition="c", severity="error", rationale="r")
    assert bare.check is None

    def _always_true(solution: Solution) -> bool:
        return True

    checked = Invariant(name="n2", condition="c2", severity="error", rationale="r2", check=_always_true)
    assert checked.check is not None
    assert checked.check(Solution(content="x", format="text", sources=[])) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_protocols.py::test_invariant_check_field_defaults_to_none_and_accepts_a_callable -v`
Expected: FAIL with `TypeError: Invariant.__init__() got an unexpected keyword argument 'check'`

- [ ] **Step 3: Add the field**

In `src/ooagent/core/protocols.py`, locate the `Invariant` dataclass (lines 47-52):

```python
@dataclass(frozen=True)
class Invariant:
    name: str
    condition: str
    severity: Literal["error", "warning"]
    rationale: str
```

Replace with:

```python
@dataclass(frozen=True)
class Invariant:
    name: str
    condition: str
    severity: Literal["error", "warning"]
    rationale: str
    check: Callable[[Solution], bool] | None = None
```

Confirm `Callable` is already imported in `protocols.py` (it is used elsewhere in the file for other callable-typed fields such as `StateObserver`/`ResponseDecoratorFn`); if the top-of-file import block does not already include `from collections.abc import Callable`, add it. `Solution` is defined earlier in the same file (lines 160-165), so no import is needed — but `Invariant` must appear *after* `Solution` in file order for the forward reference to resolve without `from __future__ import annotations` issues; `protocols.py` already has `from __future__ import annotations` at the top (standard for this codebase), so forward references by name are fine regardless of definition order.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_protocols.py::test_invariant_check_field_defaults_to_none_and_accepts_a_callable -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/protocols.py tests/core/test_protocols.py
git commit -m "feat(core): add optional check callable to Invariant"
```

---

### Task 2: Make `ConstraintEngine._assert` actually enforce invariants

**Files:**
- Modify: `src/ooagent/core/pipeline.py:59-67` (`ConstraintEngine.assert_all` / `_assert`)
- Test: `tests/core/test_pipeline.py`

**Interfaces:**
- Consumes: `Invariant.check` from Task 1.
- Produces: `ConstraintEngine._assert(solution: Solution, invariant: Invariant) -> None` — raises `ConstraintViolationError` when `invariant.check` is present, returns `False`, and `invariant.severity == "error"`. Silently passes when `check is None`, when `check(solution)` returns `True`, or when severity is `"warning"` (warnings are non-fatal by design — CLAUDE.md §11 defines severity as `error | warning` precisely to distinguish halting from non-halting invariants).

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/test_pipeline.py` (after the existing `test_constraint_engine_assert_all_does_not_raise_by_default` test at line 59):

```python
def test_constraint_engine_raises_on_failing_error_severity_invariant() -> None:
    from ooagent.core.protocols import ConstraintViolationError, Invariant

    engine = ConstraintEngine.get_instance()
    solution = Solution(content="ok", format="text", sources=[])
    failing = Invariant(
        name="always-fails",
        condition="never true",
        severity="error",
        rationale="test",
        check=lambda s: False,
    )
    with pytest.raises(ConstraintViolationError) as exc_info:
        engine.assert_all(solution, [failing])
    assert exc_info.value.invariant_name == "always-fails"


def test_constraint_engine_does_not_raise_on_failing_warning_severity_invariant() -> None:
    from ooagent.core.protocols import Invariant

    engine = ConstraintEngine.get_instance()
    solution = Solution(content="ok", format="text", sources=[])
    warning = Invariant(
        name="soft-check",
        condition="never true",
        severity="warning",
        rationale="test",
        check=lambda s: False,
    )
    engine.assert_all(solution, [warning])  # should not raise


def test_constraint_engine_does_not_raise_on_passing_invariant() -> None:
    from ooagent.core.protocols import Invariant

    engine = ConstraintEngine.get_instance()
    solution = Solution(content="ok", format="text", sources=[])
    passing = Invariant(
        name="always-passes", condition="x", severity="error", rationale="test", check=lambda s: True
    )
    engine.assert_all(solution, [passing])  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_pipeline.py::test_constraint_engine_raises_on_failing_error_severity_invariant -v`
Expected: FAIL (no exception raised — the no-op `_assert` currently never raises)

- [ ] **Step 3: Implement real enforcement**

In `src/ooagent/core/pipeline.py`, replace lines 59-67:

```python
    def assert_all(self, solution: Solution, invariants: list[Invariant]) -> None:
        for inv in invariants:
            self._assert(solution, inv)

    def _assert(self, solution: Solution, invariant: Invariant) -> None:
        """Base evaluation: domain contexts provide specialized validators via
        IDomainContext.invariants() whose conditions are checked at runtime.
        Override this method in subclasses to add custom validation logic.
        The base engine passes all invariants — domain contexts narrow this."""
```

with:

```python
    def assert_all(self, solution: Solution, invariants: list[Invariant]) -> None:
        for inv in invariants:
            self._assert(solution, inv)

    def _assert(self, solution: Solution, invariant: Invariant) -> None:
        """Evaluates `invariant.check(solution)` when a check callable is
        supplied. An invariant with no check (`check=None`) is documentation-
        only and always passes — CONTEXT.md-declared invariants (§14 CLAUDE.md)
        that a domain has not wired a predicate for yet remain non-blocking
        rather than silently fabricating a pass/fail verdict. A failing
        `severity="error"` invariant halts the turn; a failing
        `severity="warning"` invariant does not (§11 CLAUDE.md)."""
        if invariant.check is None:
            return
        if invariant.check(solution):
            return
        if invariant.severity == "error":
            raise ConstraintViolationError(invariant.name, solution.content, {"condition": invariant.condition})
```

`ConstraintViolationError` is already imported at the top of `pipeline.py` (line 9).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_pipeline.py -v`
Expected: all PASS, including the 3 new tests and the pre-existing `test_constraint_engine_assert_all_does_not_raise_by_default` (still passes — empty invariants list).

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/pipeline.py tests/core/test_pipeline.py
git commit -m "fix(core): ConstraintEngine actually enforces invariants with a check callable"
```

---

### Task 3: Inject `ConstraintEngine` into `OOAgent` (DIP)

**Files:**
- Modify: `src/ooagent/core/agent.py:96-121` (`OOAgent.__init__`)
- Test: `tests/core/test_agent.py`

**Interfaces:**
- Consumes: `ConstraintEngine` from `ooagent.core.pipeline` (Task 2).
- Produces: `OOAgent(..., constraint_engine: ConstraintEngine | None = None)` — when omitted, behavior is unchanged (`ConstraintEngine.get_instance()`, the existing singleton).

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_agent.py` (after `test_agent_id_is_generated_when_not_supplied`, around line 88):

```python
async def test_constraint_engine_is_injectable_and_defaults_to_singleton() -> None:
    from ooagent.core.pipeline import ConstraintEngine

    default_agent = OOAgent(llm_client=_StubLLMClient())
    assert default_agent._constraint_engine is ConstraintEngine.get_instance()

    custom_engine = ConstraintEngine()
    injected_agent = OOAgent(llm_client=_StubLLMClient(), constraint_engine=custom_engine)
    assert injected_agent._constraint_engine is custom_engine
    assert injected_agent._constraint_engine is not ConstraintEngine.get_instance()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_agent.py::test_constraint_engine_is_injectable_and_defaults_to_singleton -v`
Expected: FAIL with `TypeError: OOAgent.__init__() got an unexpected keyword argument 'constraint_engine'`

- [ ] **Step 3: Add the constructor parameter**

In `src/ooagent/core/agent.py`, the `OOAgent.__init__` signature (lines 96-107):

```python
    def __init__(
        self,
        llm_client: ILLMClient,
        ctx_registry: ContextRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
        plugin_registry: PluginRegistry | None = None,
        pipeline: ResponsePipeline | None = None,
        artifact_factory: ArtifactFactory | None = None,
        decorator: ResponseDecorator | None = None,
        telemetry: ITelemetryProvider | None = None,
        id: str | None = None,
    ) -> None:
```

Add `constraint_engine: ConstraintEngine | None = None` after `pipeline`:

```python
    def __init__(
        self,
        llm_client: ILLMClient,
        ctx_registry: ContextRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
        plugin_registry: PluginRegistry | None = None,
        pipeline: ResponsePipeline | None = None,
        constraint_engine: ConstraintEngine | None = None,
        artifact_factory: ArtifactFactory | None = None,
        decorator: ResponseDecorator | None = None,
        telemetry: ITelemetryProvider | None = None,
        id: str | None = None,
    ) -> None:
```

And in the body (line 114):

```python
        self._constraint_engine = ConstraintEngine.get_instance()
```

replace with:

```python
        self._constraint_engine = constraint_engine or ConstraintEngine.get_instance()
```

`ConstraintEngine` is already imported at the top of `agent.py` (line 14: `from ooagent.core.pipeline import ConstraintEngine, ResponsePipeline`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_agent.py::test_constraint_engine_is_injectable_and_defaults_to_singleton -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/agent.py tests/core/test_agent.py
git commit -m "feat(core): make ConstraintEngine injectable into OOAgent (DIP)"
```

---

### Task 4: Add a generic empty-query pipeline step, wired as OOAgent's default base step

**Files:**
- Modify: `src/ooagent/core/pipeline.py` (add `empty_query_step` factory function, after `create_step`)
- Modify: `src/ooagent/core/agent.py:96-121` (`OOAgent.__init__`, default `pipeline`)
- Test: `tests/core/test_pipeline.py`, `tests/core/test_agent.py`

**Interfaces:**
- Consumes: `create_step` (existing, `pipeline.py:70-93`), `Query`/`IDomainContext` (existing protocols).
- Produces: `empty_query_step() -> PipelineStep` in `ooagent.core.pipeline` — a base-level (context-agnostic) CoR step that fails with `passed=False` when `query.text` is empty or whitespace-only.

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_pipeline.py`:

```python
async def test_empty_query_step_fails_on_blank_text() -> None:
    from ooagent.core.pipeline import empty_query_step

    step = empty_query_step()
    result = await step.run(Query(text="   "), object())  # type: ignore[arg-type]
    assert result.passed is False
    assert "empty" in (result.violation or "").lower()


async def test_empty_query_step_passes_on_non_blank_text() -> None:
    from ooagent.core.pipeline import empty_query_step

    step = empty_query_step()
    result = await step.run(Query(text="hello"), object())  # type: ignore[arg-type]
    assert result.passed is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_pipeline.py::test_empty_query_step_fails_on_blank_text -v`
Expected: FAIL with `ImportError: cannot import name 'empty_query_step'`

- [ ] **Step 3: Implement `empty_query_step` and wire it as the default base pipeline step**

In `src/ooagent/core/pipeline.py`, append after the `create_step` function (after line 93):

```python
def empty_query_step() -> PipelineStep:
    """Generic invariant, always on regardless of active context — §11
    CLAUDE.md. Lives at the base-pipeline level (not IDomainContext-specific)
    because every context must reject an empty query identically."""

    async def _check(query: Query, context: IDomainContext) -> dict[str, Any]:
        if not query.text or not query.text.strip():
            return {"passed": False, "violation": "Query text must not be empty"}
        return {"passed": True}

    return create_step("empty_query_guard", _check)
```

In `src/ooagent/core/agent.py`, line 113:

```python
        self._pipeline = pipeline or ResponsePipeline()
```

replace with:

```python
        self._pipeline = pipeline or ResponsePipeline([empty_query_step()])
```

Add `empty_query_step` to the `from ooagent.core.pipeline import ...` line at the top of `agent.py` (line 14):

```python
from ooagent.core.pipeline import ConstraintEngine, ResponsePipeline
```

becomes:

```python
from ooagent.core.pipeline import ConstraintEngine, ResponsePipeline, empty_query_step
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_pipeline.py -v`
Expected: all PASS.

Run: `pytest tests/core/test_agent.py -v`
Expected: all PASS (existing tests use non-empty query text, e.g. `Query(text="hi")`, so the new default step does not affect them).

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/pipeline.py src/ooagent/core/agent.py tests/core/test_pipeline.py
git commit -m "feat(core): add generic empty-query pipeline step as OOAgent's default base step"
```

---

### Task 5: Fix the GATHERING-prelude FSM bypass — route through the legal FAILURE path

**Files:**
- Modify: `src/ooagent/core/agent.py:156-166` (the `_turn()` GATHERING prelude), `agent.py:320-336` (`_handle_failure`)
- Test: `tests/core/test_agent.py`

**Interfaces:**
- Produces: `_handle_failure(self, err: Exception, context: IDomainContext | None, _snapshot_id: str) -> Artifact` — `context` is now optional; a `None` context is reported as `"unknown"` in telemetry and the built artifact, mirroring `_handle_unrecoverable_failure`'s existing fallback.

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_agent.py`:

```python
async def test_context_resolution_failure_routes_through_failure_state_not_bypass() -> None:
    # §12 CLAUDE.md: "FAILURE always leads to DELIVERING (emit error artifact)
    # then IDLE." A failure during the GATHERING prelude (context resolution)
    # has GATHERING -> FAILURE as a legal transition (state.py VALID_TRANSITIONS),
    # so it must not use the FSM-bypassing _handle_unrecoverable_failure path.
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_StubLLMClient(), telemetry=telemetry)
    await agent.initialize(AgentConfig())

    def _boom(query):
        raise RuntimeError("resolve boom")

    agent._ctx_registry.resolve = _boom  # type: ignore[method-assign]

    artifact = await agent.respond(Query(text="hello agent"))

    assert "resolve boom" in artifact.content
    assert agent.state.fsm == "IDLE"
    assert (
        "turn.failed",
        {"context": "unknown", "error_type": "RuntimeError", "recoverable": True},
    ) in telemetry.events

    await agent.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_agent.py::test_context_resolution_failure_routes_through_failure_state_not_bypass -v`
Expected: FAIL — the `recoverable: True` event is not currently emitted for this path (the current code emits `recoverable: False` via `_handle_unrecoverable_failure`, or the test fails on the assertion for that event tuple not being present).

- [ ] **Step 3: Widen `_handle_failure`'s `context` parameter and reroute the GATHERING prelude**

In `src/ooagent/core/agent.py`, replace `_handle_failure` (lines 320-336):

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

with:

```python
    def _handle_failure(
        self, err: Exception, context: IDomainContext | None, _snapshot_id: str
    ) -> Artifact:
        context_name = context.name if context is not None else "unknown"
        self._state.transition("FAILURE")
        self._telemetry.event(
            "turn.failed",
            {"context": context_name, "error_type": type(err).__name__, "recoverable": True},
        )
        if isinstance(err, ScopeExitError):
            artifact = self._artifact_factory.build_scope_exit(context_name, err.query)
        elif isinstance(err, ConstraintViolationError):
            artifact = self._artifact_factory.build_error(str(err), context_name)
        else:
            artifact = self._artifact_factory.build_error(str(err), context_name)
        self._state.transition("DELIVERING")
        self._state.reset()
        return artifact
```

Then replace the GATHERING prelude except-block (lines 160-166):

```python
            try:
                context = self._ctx_registry.resolve(query)
                self._state.set_context(context.name)
                pipeline = self._pipeline.extend(context.pipeline())
                snapshot = self._state.snapshot()
            except Exception as err:
                return self._handle_unrecoverable_failure(err, None)
```

with:

```python
            try:
                context = self._ctx_registry.resolve(query)
                self._state.set_context(context.name)
                pipeline = self._pipeline.extend(context.pipeline())
                snapshot = self._state.snapshot()
            except Exception as err:
                return self._handle_failure(err, None, "")
```

Do **not** change the DELIVERING except-block (lines 215-216, `return self._handle_unrecoverable_failure(err, context)`) — `VALID_TRANSITIONS["DELIVERING"] = {"IDLE"}` makes `DELIVERING → FAILURE` genuinely illegal, so the bypass there is a deliberate, already-documented tradeoff (see the docstring on `_handle_unrecoverable_failure`), not a bug this task fixes.

- [ ] **Step 4: Run test to verify it passes, and confirm no regressions**

Run: `pytest tests/core/test_agent.py -v`
Expected: all PASS, including the new test and the pre-existing `test_respond_recovers_when_artifact_factory_raises_during_delivering` (which exercises the DELIVERING path this task deliberately leaves unchanged) and `test_turn_failed_event_fires_recoverable_false_on_delivering_failure`.

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/agent.py tests/core/test_agent.py
git commit -m "fix(core): GATHERING-prelude failures route through the legal FAILURE FSM state"
```

---

### Task 6: Un-skip the 4 IAgent conformance tests in `tests/conformance/test_agent.py`

**Files:**
- Modify: `tests/conformance/test_agent.py` (entire file — replacing the 4 skipped stubs)

**Interfaces:**
- Consumes: `OOAgent`, `AgentConfig`, `LifecycleError` (from `ooagent.core.protocols`), `Query` (from `ooagent.core.protocols`), the empty-query behavior from Task 4, the FSM/turn behavior already present in `core/agent.py`.

- [ ] **Step 1: Write the tests (replacing the skip stubs) — this step doubles as "write the failing test" and "the implementation" since the underlying behavior already exists from Tasks 1-5**

Replace the full contents of `tests/conformance/test_agent.py` with:

```python
"""tests/conformance/test_agent.py — IAgent conformance suite (§17 CLAUDE.md)."""

from __future__ import annotations

import pytest

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import (
    AgentConfig,
    CompletionChunk,
    CompletionResponse,
    ILLMClient,
    LifecycleError,
    Query,
    TokenUsage,
)


class _StubLLMClient(ILLMClient):
    async def complete(self, request):
        return CompletionResponse(
            content="hello",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    async def ping(self) -> bool:
        # Defensive: present whether or not the sibling lifecycle-health-and-
        # timeouts plan (which adds ILLMClient.ping() as a new abstract
        # method) has landed yet — harmless extra method if it hasn't.
        return True

    async def stream(self, request):
        yield CompletionChunk(delta="hi", done=True)

    @property
    def model_id(self):
        return "stub-1"

    @property
    def vendor(self):
        return "anthropic"

    @property
    def max_tokens(self):
        return 4096

    @property
    def supports_tools(self):
        return False


async def test_respond_empty_query_returns_constraint_violation_artifact_not_throw() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())

    artifact = await agent.respond(Query(text=""))

    assert "[ConstraintViolation]" in artifact.content
    assert agent.state.fsm == "IDLE"
    await agent.dispose()


async def test_fsm_is_idle_before_and_after_each_complete_turn() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())

    assert agent.state.fsm == "IDLE"
    await agent.respond(Query(text="hello agent"))
    assert agent.state.fsm == "IDLE"

    await agent.dispose()


async def test_session_state_turn_increments_by_exactly_1_per_successful_turn() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())

    assert agent.state.turn == 0
    await agent.respond(Query(text="hello agent"))
    assert agent.state.turn == 1
    await agent.respond(Query(text="hello again"))
    assert agent.state.turn == 2

    await agent.dispose()


async def test_dispose_is_idempotent_calling_twice_does_not_throw() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())
    await agent.dispose()
    await agent.dispose()  # must not raise


async def test_respond_after_dispose_throws_lifecycle_error() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())
    await agent.dispose()

    with pytest.raises(LifecycleError):
        await agent.respond(Query(text="hello"))
```

- [ ] **Step 2: Run the tests to verify they currently fail on the old skipped/removed content**

Run: `pytest tests/conformance/test_agent.py -v`
Expected at this point (after Tasks 1-5 are already committed): all 5 tests PASS immediately, since Tasks 1-5 already implemented the underlying behavior. This step confirms no regression was introduced by the file rewrite itself — re-run and read the output carefully rather than assuming.

- [ ] **Step 3: N/A — no implementation step needed (behavior already exists from Tasks 1-5)**

- [ ] **Step 4: Run the full conformance + core suite**

Run: `pytest tests/conformance/ tests/core/ -v`
Expected: all PASS, 0 skipped in `tests/conformance/test_agent.py`.

- [ ] **Step 5: Commit**

```bash
git add tests/conformance/test_agent.py
git commit -m "test(conformance): un-skip and implement the 4 IAgent conformance tests"
```

---

### Task 7: Full-suite regression check and static analysis

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all PASS (coverage gate is 70%, per `.specify/gates/Makefile` — these additive tests should only raise coverage, not lower it).

- [ ] **Step 2: Run mypy --strict**

Run: `mypy --strict src/ooagent`
Expected: no errors. Pay particular attention to `Invariant.check: Callable[[Solution], bool] | None` — mypy strict requires the `Callable` import to already be present in `protocols.py` (confirm via the existing `StateObserver`/similar callable-typed fields in that file).

- [ ] **Step 3: Run ruff**

Run: `ruff check src/ooagent tests`
Expected: no errors.

- [ ] **Step 4: Commit if any lint-only fixups were needed**

```bash
git add -A
git commit -m "chore: lint/type fixups for constraint-engine and conformance work"
```

(Skip this commit entirely if steps 1-3 were already clean.)
