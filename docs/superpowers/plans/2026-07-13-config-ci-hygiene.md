# Config & CI Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close five small, independent gaps between documented/implied guarantees and actual behavior: stale unchecked boxes in `specs/001-spec-driven-workflow-layer/tasks.md` (already-merged work shown as not-done), `SessionState`'s memento eviction being FIFO despite being documented as LRU, the unreachable `DEGRADED` FSM state (declared and transition-table-complete, but no code path ever enters it — and not part of CLAUDE.md §12's documented FSM diagram at all), weak `isinstance`-only assertions in `tests/mcp/test_config.py`, and `mypy --strict`'s scope silently excluding `tests/` (CLAUDE.md §7 claims import-cycle detection covers the whole repo; it currently only covers `src/ooagent`).

**Architecture:** Each task is independent and touches a different file/concern — this plan has no internal task-ordering dependencies except that Task 5 (widening mypy's scope) should run last within this plan, since it is the one task whose outcome depends on the real state of every `.py` file under `tests/` (including any new test files landed by sibling plans in this same pass) and is most likely to surface pre-existing issues that need triage.

**Tech Stack:** Python 3.11, `collections.OrderedDict` (stdlib) for the LRU fix, mypy --strict, ruff, pytest.

## Global Constraints

- `mypy --strict` and `ruff` (`select = ["E", "F", "I", "UP", "B"]`, line-length 100) must pass on every touched file.
- No new runtime dependencies.
- `core/protocols.py`/`core/state.py` changes must not remove or alter any behavior actually exercised by existing passing tests — confirmed via full-suite re-runs after each task.
- Existing tests in `tests/core/test_state.py`, `tests/mcp/test_config.py` must continue to pass except where a task explicitly updates them.

---

### Task 1: Fix stale checkboxes in `specs/001-spec-driven-workflow-layer/tasks.md`

**Files:**
- Modify: `specs/001-spec-driven-workflow-layer/tasks.md`
- Test: `tests/workflow/test_spec_driven_workflow.py` (add a lightweight regression guard)

**Interfaces:** none (docs-only change plus a guard test).

- [ ] **Step 1: Write the failing test**

Add to `tests/workflow/test_spec_driven_workflow.py`:

```python
def test_spec_001_tasks_md_has_no_stale_unchecked_boxes() -> None:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    tasks_md = (repo_root / "specs" / "001-spec-driven-workflow-layer" / "tasks.md").read_text(
        encoding="utf-8"
    )
    assert "- [ ]" not in tasks_md, "spec 001 is fully implemented and merged — all tasks should be checked"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/workflow/test_spec_driven_workflow.py::test_spec_001_tasks_md_has_no_stale_unchecked_boxes -v`
Expected: FAIL — the file currently has 6 unchecked `- [ ]` boxes.

- [ ] **Step 3: Fix the checkboxes**

Replace the full contents of `specs/001-spec-driven-workflow-layer/tasks.md` with:

```markdown
# 001 — Tasks

- [x] **TASK-1** [P] Add `IDeliveryWorkflow` ABC and SDD value objects — file: `src/ooagent/core/protocols.py` — implements REQ-1/AC-1
  - **TEST-1**: `tests/core/test_protocols.py::test_idelivery_workflow_cannot_be_instantiated_directly`

- [x] **TASK-2** [P] Add the 8-Article constitution — file: `src/ooagent/workflow/constitution.py` — implements REQ-2/AC-2
  - **TEST-2**: `tests/workflow/test_constitution.py::test_constitution_has_exactly_eight_articles`

- [x] **TASK-3** [P] Add the 19-target gate catalog — file: `src/ooagent/workflow/gate_catalog.py` — implements REQ-3/AC-3
  - **TEST-3**: `tests/workflow/test_gate_catalog.py::test_gate_catalog_has_exactly_nineteen_targets`

- [x] **TASK-4** [P] Add traceability orphan detection — file: `src/ooagent/workflow/traceability.py` — implements REQ-4/AC-4
  - **TEST-4**: `tests/workflow/test_traceability.py::test_verify_traceability_flags_entry_missing_task_id_as_failing`

- [x] **TASK-5** Add the runnable gate Makefile — file: `.specify/gates/Makefile` — implements REQ-5/AC-5
  - **TEST-5**: `tests/workflow/test_gate_makefile.py::test_makefile_required_gates_have_non_optional_recipes`

- [x] **TASK-6** Add the verify-spec traceability checker — file: `scripts/sdd-verify-spec.sh` — implements REQ-6/AC-6
  - **TEST-6**: `tests/workflow/test_sdd_verify_spec.py::test_script_passes_on_this_repos_own_specs_directory`
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/workflow/test_spec_driven_workflow.py::test_spec_001_tasks_md_has_no_stale_unchecked_boxes -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add specs/001-spec-driven-workflow-layer/tasks.md tests/workflow/test_spec_driven_workflow.py
git commit -m "docs(specs): mark spec 001's tasks as complete — all 6 are implemented and merged"
```

---

### Task 2: Fix `SessionState` memento eviction — FIFO to real LRU

**Files:**
- Modify: `src/ooagent/core/state.py:34-44` (`SessionState.__init__`), `:77-102` (`snapshot`, `restore`)
- Test: `tests/core/test_state.py`

**Interfaces:**
- Produces: `SessionState.snapshot()`/`.restore(id)` unchanged signatures; eviction now removes the *least-recently-accessed* memento (tracked via `restore()` calls, not just insertion order) rather than the oldest-inserted one.

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_state.py`:

```python
def test_snapshot_eviction_is_lru_not_fifo() -> None:
    state = SessionState(max_mementos=2)
    state.transition("GATHERING")
    a = state.snapshot()
    state.transition("MODELING")
    b = state.snapshot()

    state.restore(a.id)  # touches `a` — makes it more-recently-used than `b`

    c = state.snapshot()  # 3rd snapshot exceeds max_mementos=2

    with pytest.raises(ValueError):
        state.restore(b.id)  # `b` was least-recently-used — evicted
    state.restore(a.id)  # must not raise — still present
    state.restore(c.id)  # must not raise — still present
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_state.py::test_snapshot_eviction_is_lru_not_fifo -v`
Expected: FAIL — under the current FIFO eviction, `a` (inserted first) is evicted instead of `b`, so `state.restore(b.id)` does not raise (it's still present) and `state.restore(a.id)` raises `ValueError` unexpectedly.

- [ ] **Step 3: Implement**

In `src/ooagent/core/state.py`, add the import (top of file, after `import uuid` at line 6):

```python
import time
import uuid
```

becomes:

```python
import time
import uuid
from collections import OrderedDict
```

Replace `__init__` (lines 35-44):

```python
    def __init__(self, max_mementos: int = 100) -> None:
        self._fsm: AgentFSMState = "IDLE"
        self._turn = 0
        self._context_name = "NullContext"
        self._scratch: dict[str, object] = {}
        self._trace: FSMTrace = []
        self._mementos: dict[str, Memento] = {}
        self._command_log: list[Command] = []
        self._observers: set[StateObserver] = set()
        self._max_mementos = max_mementos
```

with:

```python
    def __init__(self, max_mementos: int = 100) -> None:
        self._fsm: AgentFSMState = "IDLE"
        self._turn = 0
        self._context_name = "NullContext"
        self._scratch: dict[str, object] = {}
        self._trace: FSMTrace = []
        self._mementos: OrderedDict[str, Memento] = OrderedDict()
        self._command_log: list[Command] = []
        self._observers: set[StateObserver] = set()
        self._max_mementos = max_mementos
```

Replace `snapshot` (lines 77-91):

```python
    def snapshot(self) -> Memento:
        if len(self._mementos) >= self._max_mementos:
            oldest_key = next(iter(self._mementos), None)
            if oldest_key is not None:
                del self._mementos[oldest_key]
        memento = Memento(
            id=str(uuid.uuid4()),
            fsm=self._fsm,
            turn=self._turn,
            context_name=self._context_name,
            scratch=dict(self._scratch),
            timestamp=time.time(),
        )
        self._mementos[memento.id] = memento
        return memento
```

with:

```python
    def snapshot(self) -> Memento:
        if len(self._mementos) >= self._max_mementos:
            self._mementos.popitem(last=False)  # evict least-recently-used
        memento = Memento(
            id=str(uuid.uuid4()),
            fsm=self._fsm,
            turn=self._turn,
            context_name=self._context_name,
            scratch=dict(self._scratch),
            timestamp=time.time(),
        )
        self._mementos[memento.id] = memento
        return memento
```

Replace `restore` (lines 93-102):

```python
    def restore(self, id: str) -> None:
        memento = self._mementos.get(id)
        if memento is None:
            raise ValueError(f"Memento not found: {id}")
        self._fsm = memento.fsm
        self._turn = memento.turn
        self._context_name = memento.context_name
        self._scratch = dict(memento.scratch)
        self._trace = []
        self._notify_observers()
```

with:

```python
    def restore(self, id: str) -> None:
        memento = self._mementos.get(id)
        if memento is None:
            raise ValueError(f"Memento not found: {id}")
        self._mementos.move_to_end(id)  # mark as most-recently-used
        self._fsm = memento.fsm
        self._turn = memento.turn
        self._context_name = memento.context_name
        self._scratch = dict(memento.scratch)
        self._trace = []
        self._notify_observers()
```

- [ ] **Step 4: Run test to verify it passes, and confirm no regressions**

Run: `pytest tests/core/test_state.py -v`
Expected: all PASS, including the pre-existing `test_snapshot_and_restore_round_trip` and `test_restore_also_restores_turn` (both use a single memento, unaffected by eviction-order changes).

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/state.py tests/core/test_state.py
git commit -m "fix(core): SessionState memento eviction is real LRU, not FIFO"
```

---

### Task 3: Remove the unreachable `DEGRADED` FSM state

**Files:**
- Modify: `src/ooagent/core/protocols.py:16-26` (`AgentFSMState` Literal)
- Modify: `src/ooagent/core/state.py:21-31` (`VALID_TRANSITIONS`)
- Test: `tests/core/test_state.py`

**Interfaces:**
- Produces: `AgentFSMState` no longer includes `"DEGRADED"`. `VALID_TRANSITIONS` no longer has a `"DEGRADED"` key. This is a pure removal of dead, unreachable code — `DEGRADED` does not appear in CLAUDE.md §12's documented FSM diagram, and grep confirms (per this plan's fact-gathering) that no code anywhere calls `transition("DEGRADED")`; the *separate* `HealthStatus = Literal["healthy", "degraded", "unhealthy"]` vocabulary (lowercase, used by `LifecycleManager.health_check()`) is untouched and remains the sole "degraded" concept.

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_state.py`:

```python
def test_degraded_is_not_a_valid_fsm_state() -> None:
    from ooagent.core.state import VALID_TRANSITIONS

    assert "DEGRADED" not in VALID_TRANSITIONS
    for targets in VALID_TRANSITIONS.values():
        assert "DEGRADED" not in targets
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_state.py::test_degraded_is_not_a_valid_fsm_state -v`
Expected: FAIL — `"DEGRADED"` is currently a key in `VALID_TRANSITIONS`.

- [ ] **Step 3: Implement**

In `src/ooagent/core/protocols.py`, the `AgentFSMState` Literal (lines 16-26):

```python
AgentFSMState = Literal[
    "IDLE",
    "GATHERING",
    "AWAITING",
    "MODELING",
    "SOLVING",
    "VALIDATING",
    "DELIVERING",
    "FAILURE",
    "DEGRADED",
]
```

becomes:

```python
AgentFSMState = Literal[
    "IDLE",
    "GATHERING",
    "AWAITING",
    "MODELING",
    "SOLVING",
    "VALIDATING",
    "DELIVERING",
    "FAILURE",
]
```

In `src/ooagent/core/state.py`, `VALID_TRANSITIONS` (lines 21-31):

```python
VALID_TRANSITIONS: dict[AgentFSMState, set[AgentFSMState]] = {
    "IDLE": {"GATHERING"},
    "GATHERING": {"MODELING", "AWAITING", "FAILURE"},
    "AWAITING": {"MODELING", "FAILURE"},
    "MODELING": {"SOLVING", "FAILURE"},
    "SOLVING": {"VALIDATING", "FAILURE"},
    "VALIDATING": {"DELIVERING", "FAILURE"},
    "DELIVERING": {"IDLE"},
    "FAILURE": {"DELIVERING"},
    "DEGRADED": {"IDLE", "FAILURE"},
}
```

becomes:

```python
VALID_TRANSITIONS: dict[AgentFSMState, set[AgentFSMState]] = {
    "IDLE": {"GATHERING"},
    "GATHERING": {"MODELING", "AWAITING", "FAILURE"},
    "AWAITING": {"MODELING", "FAILURE"},
    "MODELING": {"SOLVING", "FAILURE"},
    "SOLVING": {"VALIDATING", "FAILURE"},
    "VALIDATING": {"DELIVERING", "FAILURE"},
    "DELIVERING": {"IDLE"},
    "FAILURE": {"DELIVERING"},
}
```

- [ ] **Step 4: Run test to verify it passes, and confirm no regressions**

Run: `pytest tests/core/test_state.py -v`
Expected: all PASS.

Run: `pytest -q`
Expected: all PASS repo-wide — confirms no test anywhere depended on the `"DEGRADED"` FSM literal (only `HealthStatus`'s lowercase `"degraded"` string is used by any test, per this plan's fact-gathering, and that type is untouched).

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/core/protocols.py src/ooagent/core/state.py tests/core/test_state.py
git commit -m "fix(core): remove the unreachable DEGRADED FSM state (not in the §12 diagram, never entered)"
```

---

### Task 4: Strengthen `tests/mcp/test_config.py`'s LLM-client-construction assertions

**Files:**
- Modify: `tests/mcp/test_config.py`

**Interfaces:** none new — strengthens existing test assertions only.

- [ ] **Step 1: Confirm the exact config field name, then write the strengthened tests**

`src/ooagent/mcp/config.py` calls `AnthropicConfig(api_key=api_key)`, `OpenAIConfig(api_key=api_key)`, and `GeminiConfig(api_key=api_key)` (confirmed — `api_key` is a real keyword argument accepted by all three `*Config` dataclasses). Before writing the assertions, read `src/ooagent/adapters/llm/anthropic.py` to confirm the concrete `AnthropicLLMClient` stores its config on a `self._config` attribute (mirroring the access pattern this repo already uses elsewhere, e.g. `agent._constraint_engine`, `agent._tool_registry` in `tests/core/test_agent.py`) — if the attribute has a different name, use that name instead in the assertions below.

Replace `tests/mcp/test_config.py`'s four bare-`isinstance` tests:

```python
def test_build_llm_client_anthropic() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "anthropic", "ANTHROPIC_API_KEY": "key-1"})
    assert isinstance(client, AnthropicLLMClient)


def test_build_llm_client_openai() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "openai", "OPENAI_API_KEY": "key-2"})
    assert isinstance(client, OpenAILLMClient)


def test_build_llm_client_gemini() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "gemini", "GEMINI_API_KEY": "key-3"})
    assert isinstance(client, GeminiLLMClient)


def test_build_llm_client_ollama_needs_no_api_key() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "ollama"})
    assert isinstance(client, OllamaLLMClient)
```

with:

```python
def test_build_llm_client_anthropic() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "anthropic", "ANTHROPIC_API_KEY": "key-1"})
    assert isinstance(client, AnthropicLLMClient)
    assert client._config.api_key == "key-1"


def test_build_llm_client_openai() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "openai", "OPENAI_API_KEY": "key-2"})
    assert isinstance(client, OpenAILLMClient)
    assert client._config.api_key == "key-2"


def test_build_llm_client_gemini() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "gemini", "GEMINI_API_KEY": "key-3"})
    assert isinstance(client, GeminiLLMClient)
    assert client._config.api_key == "key-3"


def test_build_llm_client_ollama_needs_no_api_key() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "ollama"})
    assert isinstance(client, OllamaLLMClient)
    assert hasattr(client, "_config")
```

If the confirmation read in this step shows the config is stored under a different attribute name than `_config`, substitute that name consistently across all four assertions above before proceeding.

- [ ] **Step 2: Run tests to verify they fail (or pass, confirming the attribute name)**

Run: `pytest tests/mcp/test_config.py -v`
Expected: if `_config` is indeed the storage attribute, all 4 modified tests PASS immediately — this step is a confirmation, not a red/green cycle in the usual sense, since the underlying wiring (`build_llm_client` passing `api_key=` through) already exists and works. If any test fails with an `AttributeError`, that confirms the attribute name guess was wrong — go back to Step 1 and correct it.

- [ ] **Step 3: N/A if Step 2 passed — no source change needed, only the test strengthening from Step 1**

- [ ] **Step 4: Run the full mcp test suite**

Run: `pytest tests/mcp/ -v`
Expected: all PASS, including the pre-existing `test_build_llm_client_missing_vendor_raises`, `test_build_llm_client_unsupported_vendor_raises`, `test_build_llm_client_anthropic_missing_key_raises`, `test_build_agent_returns_agent_and_null_context` (unmodified, still passing).

- [ ] **Step 5: Commit**

```bash
git add tests/mcp/test_config.py
git commit -m "test(mcp): assert build_llm_client actually wires the api_key through, not just the class"
```

---

### Task 5: Widen `mypy --strict`'s scope to include `tests/`

**Files:**
- Modify: `pyproject.toml` (`[tool.mypy]` section)
- Modify: any test file that surfaces a genuine, cheap-to-fix type error (missing parameter/return annotation, wrong type) once the scope is widened

**Interfaces:** none — configuration change plus incidental test-file annotation fixes.

- [ ] **Step 1: Check what actually exists under `scripts/` and `examples/` before deciding scope**

Run: `git ls-files 'scripts/*.py' 'examples/*.py'`

If this returns no output, neither directory contains Python source — mypy has nothing to check there, and CLAUDE.md §7's claim only meaningfully applies to `tests/` in that case. If it returns file paths, include that directory's glob in the `files` list in Step 3 the same way `tests` is included below.

- [ ] **Step 2: Widen the mypy config and run it to see what surfaces**

In `pyproject.toml`, replace the `[tool.mypy]` section:

```toml
[tool.mypy]
strict = true
python_version = "3.11"
packages = ["ooagent"]
```

with:

```toml
[tool.mypy]
strict = true
python_version = "3.11"
packages = ["ooagent"]
files = ["tests"]

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_incomplete_defs = false
```

(If Step 1 found `.py` files under `scripts/` or `examples/`, add them to the `files` list, e.g. `files = ["tests", "scripts", "examples"]`, and extend the override's `module` glob accordingly, e.g. `module = "tests.*|scripts.*|examples.*"` — mypy overrides accept a single string or a list of module globs; consult `mypy --help` / the mypy config docs for this version if the glob syntax needs adjusting.)

The override relaxes only `disallow_untyped_defs`/`disallow_incomplete_defs` — the two strict sub-flags that would otherwise fail on the many pytest fixture parameters (`tmp_path`, `monkeypatch`, `capsys`, etc.) this codebase does not uniformly annotate by convention. Every other strict check (unreachable code, `Any`-leak warnings on non-fixture code, import resolution, redefinition, etc.) still applies to `tests/`.

Run: `mypy --strict src/ooagent tests`

- [ ] **Step 3: Triage and fix what the run in Step 2 surfaces**

Read the full error list. For each error:
- If it is a genuine bug (wrong type passed, undefined name, import cycle, unreachable code) — fix it directly in the affected test file. This is real signal the widened scope was meant to catch.
- If it is purely a missing annotation on a *non-fixture* parameter or local variable (something this plan's own new test code across sibling plans may have introduced, e.g. an untyped `tmp_path` parameter or an untyped helper function) — add the missing annotation rather than suppressing it; these are cheap, mechanical fixes (e.g. `def test_foo(tmp_path) -> None:` becomes `def test_foo(tmp_path: Path) -> None:`, adding `from pathlib import Path` if not already imported in that file).
- Do not add blanket suppressions (`# type: ignore` without a specific error code, or widening the override beyond `disallow_untyped_defs`/`disallow_incomplete_defs`) to make errors disappear — every error must be either fixed or, if truly unfixable within this task's scope (e.g. a third-party stub gap unrelated to this repo's own code), given a narrowly-scoped `# type: ignore[<specific-code>]` with a one-line comment explaining why.

This step's effort is bounded by what actually surfaces — it cannot be fully scripted in advance since the real error count against the live `tests/` tree was not knowable during planning.

- [ ] **Step 4: Run mypy and the full test suite to confirm everything is clean**

Run: `mypy --strict src/ooagent tests`
Expected: no errors.

Run: `pytest -q`
Expected: all PASS — confirms none of the annotation fixes in Step 3 changed runtime behavior.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests
git commit -m "chore(ci): widen mypy --strict scope to include tests/ (was src/ooagent only)"
```

---

### Task 6: Full-suite regression check and static analysis

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all PASS.

- [ ] **Step 2: Run mypy --strict**

Run: `mypy --strict src/ooagent tests`
Expected: no errors.

- [ ] **Step 3: Run ruff**

Run: `ruff check src/ooagent tests`
Expected: no errors.

- [ ] **Step 4: Commit if any lint-only fixups were needed**

```bash
git add -A
git commit -m "chore: lint/type fixups for config/CI hygiene work"
```

(Skip this commit entirely if steps 1-3 were already clean.)
