# SpecDrivenWorkflow / IDeliveryWorkflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `IDeliveryWorkflow` / `SpecDrivenWorkflow` as a fourth OOC layer for OOAgent — a gate-enforced software-delivery methodology, orthogonal to `IDomainContext`, plus the `.specify/` scaffold, CI gate, and docs that make it real and self-hosted (dogfooded on this very feature).

**Architecture:** A new `IDeliveryWorkflow` ABC joins the interface catalog in `core/protocols.py`. `SpecDrivenWorkflow` (its sole implementation) lives in a new `src/ooagent/workflow/` package and holds the 8-Article constitution, the 11-phase pipeline, the 19-target gate catalog, and traceability-matrix orphan detection as real, tested Python objects — never invoked from `core/agent.py`'s `respond()` path. A parallel `.specify/` scaffold (constitution.md, templates, gates/Makefile) plus a new additive CI workflow (`sdd-gate.yml`) and a bash traceability checker (`scripts/sdd-verify-spec.sh`) make the gate contract runnable, not just documented. The feature specifies itself under `specs/001-spec-driven-workflow-layer/` to prove the traceability gate on day one.

**Tech Stack:** Python 3.11, `uv`, `mypy --strict`, `ruff`, `pytest` + `pytest-cov` (existing repo stack — see `docs/superpowers/specs/2026-07-04-python-port-design.md`). Bash for the new gate script (matches `scripts/ai-safety-gate.sh` style). GNU Make for `.specify/gates/Makefile` (present on `ubuntu-latest` CI runners; **not** available in this Windows dev/worktree environment — see Global Constraints).

## Global Constraints

- Full design: `docs/superpowers/specs/2026-07-06-spec-driven-workflow-design.md`. Every task below implements a named section of it.
- `IDeliveryWorkflow` is a peer architectural layer, **not** a step in `core/agent.py`'s `respond()` Template Method. No task in this plan modifies `core/agent.py`, `core/pipeline.py`, or any existing `core/*.py` file's *behavior* — only `core/protocols.py` gains new, additive definitions.
- None of the existing 6 Gitflow workflows (`ci-core.yml`, `develop-integration.yml`, `feature-pr.yml`, `hotfix.yml`, `release.yml`, `ci-autofix.yml`) are modified. The new `sdd-gate.yml` is additive.
- `make` is **not installed** in this Windows dev/worktree environment. Any task step that would normally run `make -f .specify/gates/Makefile <target>` instead (a) runs the underlying command directly (e.g. `bash scripts/sdd-verify-spec.sh`, `uv run mypy --strict`) to prove the recipe body works, and (b) verifies Makefile *syntax* via the structural test in Task 7 (`test_gate_makefile.py`) rather than actually invoking `make`. Real end-to-end Makefile execution is proven in CI by Task 9's `sdd-gate.yml`, which runs on `ubuntu-latest` (has `make` preinstalled).
- All new frozen value objects (`Phase`, `Article`, `GateSpec`, `TraceabilityEntry`, `GateResult`) go in `core/protocols.py`, matching the existing convention (see `Term`, `ProblemClass`, `Invariant`, `AntiPattern` in that file) — `@dataclass(frozen=True)`, no methods, stdlib-only imports (`core/protocols.py` has zero runtime dependencies — CLAUDE.md §7).
- All new Python modules use `from __future__ import annotations` and full type hints (`mypy --strict` must stay clean — this is enforced today by `ci-core.yml`).
- Coverage floor for `coverage-gate`: **70%** (current baseline measured at 71%; this plan's own new modules ship with their own tests and must not drop the total below 70%).
- Run `PYTHONPATH=src uv run pytest tests/ -q` after every task to confirm the full suite (old + new) stays green — not just the new task's own tests.

---

### Task 1: `IDeliveryWorkflow` value objects and ABC in `core/protocols.py`

**Files:**
- Modify: `src/ooagent/core/protocols.py` (append a new section after the existing `class IObservable(ABC):` block, which currently ends the file at line 587)
- Test: `tests/core/test_protocols.py` (append new test functions)

**Interfaces:**
- Consumes: nothing new — uses `ABC`/`abstractmethod`/`dataclass`, already imported at the top of `protocols.py`.
- Produces: `Phase`, `Article`, `GateSpec`, `TraceabilityEntry`, `GateResult` (frozen dataclasses) and `IDeliveryWorkflow` (ABC) — every later task imports these from `ooagent.core.protocols`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_protocols.py` (add these imports to the existing `from ooagent.core.protocols import (...)` block: `Article, GateResult, GateSpec, IDeliveryWorkflow, Phase, TraceabilityEntry`, keeping the existing imports `AgentConfig, IAgent, ILLMClient, Query, ToolExecutionError` and alphabetical order):

```python
def test_idelivery_workflow_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        IDeliveryWorkflow()  # type: ignore[abstract]


def test_phase_is_a_frozen_dataclass() -> None:
    p = Phase(
        name="/specify",
        artifact="spec.md",
        itil_stage="Engage",
        cobit_domain="APO",
        owasp_gate="abuse-cases noted",
        oop_pattern="-",
    )
    with pytest.raises(FrozenInstanceError):
        p.name = "changed"  # type: ignore[misc]


def test_article_is_a_frozen_dataclass() -> None:
    a = Article(numeral="I", title="Form", body="...", key="form")
    with pytest.raises(FrozenInstanceError):
        a.title = "changed"  # type: ignore[misc]


def test_gate_spec_is_a_frozen_dataclass() -> None:
    g = GateSpec(name="lint", required=True, intent="linter, zero warnings")
    with pytest.raises(FrozenInstanceError):
        g.required = False  # type: ignore[misc]


def test_traceability_entry_allows_none_for_unresolved_fields() -> None:
    entry = TraceabilityEntry(
        req_id="REQ-1",
        ac_id="AC-1",
        task_id=None,
        test_id=None,
        code_ref=None,
        ci_evidence=None,
    )
    assert entry.task_id is None
    assert entry.test_id is None


def test_gate_result_is_a_frozen_dataclass() -> None:
    r = GateResult(gate_name="verify-spec", passed=True, message="ok")
    with pytest.raises(FrozenInstanceError):
        r.passed = False  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src uv run pytest tests/core/test_protocols.py -v`
Expected: FAIL with `ImportError: cannot import name 'IDeliveryWorkflow' from 'ooagent.core.protocols'` (or similar for the other new names).

- [ ] **Step 3: Implement the minimal code**

Append this new section to `src/ooagent/core/protocols.py`, immediately after the existing `class IObservable(ABC):` block (i.e., as the new end of the file — do not touch anything above it):

```python


# ── Delivery workflow (SDD) value objects & interface ──────────────────────


@dataclass(frozen=True)
class Phase:
    name: str
    artifact: str
    itil_stage: str
    cobit_domain: str
    owasp_gate: str
    oop_pattern: str


@dataclass(frozen=True)
class Article:
    numeral: str
    title: str
    body: str
    key: str


@dataclass(frozen=True)
class GateSpec:
    name: str
    required: bool
    intent: str


@dataclass(frozen=True)
class TraceabilityEntry:
    req_id: str
    ac_id: str
    task_id: str | None
    test_id: str | None
    code_ref: str | None
    ci_evidence: str | None


@dataclass(frozen=True)
class GateResult:
    gate_name: str
    passed: bool
    message: str


class IDeliveryWorkflow(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    def phases(self) -> tuple[Phase, ...]: ...

    @abstractmethod
    def constitution(self) -> tuple[Article, ...]: ...

    @abstractmethod
    def gate_targets(self) -> dict[str, GateSpec]: ...

    @abstractmethod
    def gate_chain(self, phase_name: str) -> tuple[str, ...]: ...

    @abstractmethod
    def verify_traceability(
        self, entries: tuple[TraceabilityEntry, ...]
    ) -> tuple[GateResult, ...]: ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src uv run pytest tests/core/test_protocols.py -v`
Expected: PASS (all tests, old and new)

- [ ] **Step 5: Type-check**

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check`
Expected: mypy reports `Success: no issues found`; ruff check and format --check both report no findings (empty output, exit 0)

- [ ] **Step 6: Commit**

```bash
git add src/ooagent/core/protocols.py tests/core/test_protocols.py
git commit -m "feat(workflow): add IDeliveryWorkflow ABC and SDD value objects to core/protocols.py"
```

---

### Task 2: `workflow/constitution.py` — the 8 Articles

**Files:**
- Create: `src/ooagent/workflow/__init__.py` (empty placeholder in this task — populated with real exports in Task 5)
- Create: `src/ooagent/workflow/constitution.py`
- Test: `tests/workflow/__init__.py` (empty, marks the test package)
- Test: `tests/workflow/test_constitution.py`

**Interfaces:**
- Consumes: `Article` from `ooagent.core.protocols` (Task 1).
- Produces: `ARTICLES: tuple[Article, ...]` — consumed by Task 5's `SpecDrivenWorkflow.constitution()`.

- [ ] **Step 1: Create the empty package markers**

Create `src/ooagent/workflow/__init__.py`:

```python
"""ooagent/workflow/__init__.py — barrel export for the SpecDrivenWorkflow (SDD) layer."""

from __future__ import annotations
```

Create `tests/workflow/__init__.py`:

```python
```

(empty file — matches the existing `tests/core/__init__.py` / `tests/plugins/__init__.py` pattern of empty package markers)

- [ ] **Step 2: Write the failing test**

Create `tests/workflow/test_constitution.py`:

```python
"""tests/workflow/test_constitution.py — the 8-Article SDD constitution."""

from __future__ import annotations

from ooagent.workflow.constitution import ARTICLES


def test_constitution_has_exactly_eight_articles() -> None:
    assert len(ARTICLES) == 8


def test_constitution_numerals_are_roman_one_through_eight_in_order() -> None:
    expected = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
    assert [a.numeral for a in ARTICLES] == expected


def test_constitution_keys_are_unique() -> None:
    keys = [a.key for a in ARTICLES]
    assert len(keys) == len(set(keys))


def test_constitution_titles_match_expected_names() -> None:
    expected_titles = [
        "Form",
        "Security",
        "Governance",
        "Lifecycle",
        "Architecture",
        "Testing",
        "Zero Defects",
        "Traceability",
    ]
    assert [a.title for a in ARTICLES] == expected_titles
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=src uv run pytest tests/workflow/test_constitution.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ooagent.workflow.constitution'`

- [ ] **Step 4: Write the implementation**

Create `src/ooagent/workflow/constitution.py`:

```python
"""ooagent/workflow/constitution.py — the 8 Articles of the SDD constitution.

Human-readable projection: .specify/memory/constitution.md. Keep both in
sync — this module is the machine-readable source of truth.
"""

from __future__ import annotations

from ooagent.core.protocols import Article

ARTICLES: tuple[Article, ...] = (
    Article(
        numeral="I",
        title="Form",
        body=(
            "Artifact-first, typed, no filler, source-tagged. Every numeric "
            "claim carries a unit and a SourceTag (measured/assumed/cited/"
            "derived), per CLAUDE.md §15 Output Discipline."
        ),
        key="form",
    ),
    Article(
        numeral="II",
        title="Security",
        body=(
            "Secure-by-default; OWASP baseline enforced by the existing AI "
            "Safety Gate (13 guards), gitleaks secret scanning, and "
            "pip-audit dependency auditing. Gates block, they do not warn."
        ),
        key="security",
    ),
    Article(
        numeral="III",
        title="Governance",
        body=(
            "Client Accountable / engineer Responsible; every gate run is "
            "ledger-audited in .specify/ledger/audit.log."
        ),
        key="governance",
    ),
    Article(
        numeral="IV",
        title="Lifecycle",
        body=(
            "Gitflow (develop -> release/hotfix -> master) is the "
            "change-controlled lifecycle; every merge is a change record."
        ),
        key="lifecycle",
    ),
    Article(
        numeral="V",
        title="Architecture",
        body=(
            "SOLID/GRASP/GoF as codified in CLAUDE.md §§2-4; patterns "
            "reified as real objects, not comments. Default algorithmic "
            "complexity <= O(n); annotate deviations."
        ),
        key="architecture",
    ),
    Article(
        numeral="VI",
        title="Testing",
        body=(
            "TDD, non-negotiable: no implementation code before an "
            "approved failing test (Red), matching this repo's "
            "subagent-driven-development practice."
        ),
        key="testing",
    ),
    Article(
        numeral="VII",
        title="Zero Defects",
        body=(
            "Every requirement is testable; defect-escape-rate target is "
            "zero. Coverage floor enforced by the coverage-gate target and "
            "ratchets upward only, never down."
        ),
        key="zero-defects",
    ),
    Article(
        numeral="VIII",
        title="Traceability",
        body=(
            "spec -> task -> code -> test -> CI evidence, bidirectional, "
            "source-tagged. Orphans (code without a requirement, or a "
            "requirement without a test) are defects."
        ),
        key="traceability",
    ),
)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/workflow/test_constitution.py -v`
Expected: PASS

- [ ] **Step 6: Type-check and commit**

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check`
Expected: mypy reports `Success: no issues found`; ruff check and format --check both report no findings (empty output, exit 0)

```bash
git add src/ooagent/workflow/__init__.py src/ooagent/workflow/constitution.py tests/workflow/__init__.py tests/workflow/test_constitution.py
git commit -m "feat(workflow): add the 8-Article SDD constitution"
```

---

### Task 3: `workflow/gate_catalog.py` — the 19-target gate contract

**Files:**
- Create: `src/ooagent/workflow/gate_catalog.py`
- Test: `tests/workflow/test_gate_catalog.py`

**Interfaces:**
- Consumes: `GateSpec` from `ooagent.core.protocols` (Task 1).
- Produces: `GATE_TARGETS: dict[str, GateSpec]` — consumed by Task 5's `SpecDrivenWorkflow.gate_targets()` and Task 7's `test_gate_makefile.py` (checks every key has a Makefile recipe).

- [ ] **Step 1: Write the failing test**

Create `tests/workflow/test_gate_catalog.py`:

```python
"""tests/workflow/test_gate_catalog.py — the 19-target gate contract (§5)."""

from __future__ import annotations

from ooagent.workflow.gate_catalog import GATE_TARGETS

CONDITIONAL_GATES = (
    "migrate",
    "build",
    "sign",
    "e2e",
    "verify-signature",
    "deploy",
    "smoke",
    "dast",
    "alerting-probe",
)

REQUIRED_GATES = (
    "verify-spec",
    "typecheck",
    "lint",
    "format-check",
    "sast",
    "sca",
    "secret-scan",
    "test",
    "coverage-gate",
    "ledger",
)


def test_gate_catalog_has_exactly_nineteen_targets() -> None:
    assert len(GATE_TARGETS) == 19


def test_gate_catalog_key_matches_each_specs_name() -> None:
    for key, spec in GATE_TARGETS.items():
        assert key == spec.name


def test_required_gates_are_marked_required() -> None:
    for name in REQUIRED_GATES:
        assert GATE_TARGETS[name].required is True, f"{name} must be required"


def test_conditional_gates_are_not_required() -> None:
    for name in CONDITIONAL_GATES:
        assert GATE_TARGETS[name].required is False, f"{name} must not be required"


def test_required_and_conditional_gates_cover_the_full_catalog() -> None:
    assert set(REQUIRED_GATES) | set(CONDITIONAL_GATES) == set(GATE_TARGETS.keys())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src uv run pytest tests/workflow/test_gate_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ooagent.workflow.gate_catalog'`

- [ ] **Step 3: Write the implementation**

Create `src/ooagent/workflow/gate_catalog.py`:

```python
"""ooagent/workflow/gate_catalog.py — the 19-target gate contract (§5).

The DIP seam: this catalog declares gate NAMES and whether each is
required. Concrete execution commands live in .specify/gates/Makefile —
this module never shells out to run a tool.
"""

from __future__ import annotations

from ooagent.core.protocols import GateSpec

GATE_TARGETS: dict[str, GateSpec] = {
    "verify-spec": GateSpec(
        name="verify-spec",
        required=True,
        intent="SDD artifacts present + traceability resolved (§6)",
    ),
    "typecheck": GateSpec(
        name="typecheck",
        required=True,
        intent="static type verification",
    ),
    "lint": GateSpec(
        name="lint",
        required=True,
        intent="linter, zero warnings",
    ),
    "format-check": GateSpec(
        name="format-check",
        required=True,
        intent="formatter in check mode",
    ),
    "sast": GateSpec(
        name="sast",
        required=True,
        intent="static security analysis (OWASP ruleset)",
    ),
    "sca": GateSpec(
        name="sca",
        required=True,
        intent="dependency scan + SBOM emit (A03)",
    ),
    "secret-scan": GateSpec(
        name="secret-scan",
        required=True,
        intent="secret detection (A02)",
    ),
    "migrate": GateSpec(
        name="migrate",
        required=False,
        intent="apply schema migrations (if-db)",
    ),
    "test": GateSpec(
        name="test",
        required=True,
        intent="unit + integration + contract; emit coverage",
    ),
    "coverage-gate": GateSpec(
        name="coverage-gate",
        required=True,
        intent="fail below constitution threshold (ARTICLE VII)",
    ),
    "build": GateSpec(
        name="build",
        required=False,
        intent="build deployable/distributable (if-artifact)",
    ),
    "sign": GateSpec(
        name="sign",
        required=False,
        intent="sign artifact + provenance (A08, if-artifact)",
    ),
    "e2e": GateSpec(
        name="e2e",
        required=False,
        intent="end-to-end suite (if-ui)",
    ),
    "verify-signature": GateSpec(
        name="verify-signature",
        required=False,
        intent="verify signature before deploy (A08, if-deploy)",
    ),
    "deploy": GateSpec(
        name="deploy",
        required=False,
        intent="deploy gated on all-green (if-deploy)",
    ),
    "smoke": GateSpec(
        name="smoke",
        required=False,
        intent="post-deploy health (if-deploy)",
    ),
    "dast": GateSpec(
        name="dast",
        required=False,
        intent="dynamic security scan (if-deploy)",
    ),
    "alerting-probe": GateSpec(
        name="alerting-probe",
        required=False,
        intent="security logging/alerting reachable (A09, if-deploy)",
    ),
    "ledger": GateSpec(
        name="ledger",
        required=True,
        intent="append COBIT audit entry (ARTICLE III)",
    ),
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/workflow/test_gate_catalog.py -v`
Expected: PASS

- [ ] **Step 5: Type-check and commit**

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check`
Expected: mypy reports `Success: no issues found`; ruff check and format --check both report no findings (empty output, exit 0)

```bash
git add src/ooagent/workflow/gate_catalog.py tests/workflow/test_gate_catalog.py
git commit -m "feat(workflow): add the 19-target SDD gate contract catalog"
```

---

### Task 4: `workflow/traceability.py` — orphan detection

**Files:**
- Create: `src/ooagent/workflow/traceability.py`
- Test: `tests/workflow/test_traceability.py`

**Interfaces:**
- Consumes: `GateResult`, `TraceabilityEntry` from `ooagent.core.protocols` (Task 1).
- Produces: `verify_traceability(entries: tuple[TraceabilityEntry, ...]) -> tuple[GateResult, ...]` — consumed by Task 5's `SpecDrivenWorkflow.verify_traceability()`.

- [ ] **Step 1: Write the failing test**

Create `tests/workflow/test_traceability.py`:

```python
"""tests/workflow/test_traceability.py — §6 bidirectional traceability matrix validation."""

from __future__ import annotations

from ooagent.core.protocols import TraceabilityEntry
from ooagent.workflow.traceability import verify_traceability


def test_verify_traceability_on_empty_tuple_returns_empty_tuple() -> None:
    assert verify_traceability(()) == ()


def test_verify_traceability_flags_entry_missing_task_id_as_failing() -> None:
    entry = TraceabilityEntry(
        req_id="REQ-1",
        ac_id="AC-1",
        task_id=None,
        test_id="tests/test_x.py::test_y",
        code_ref="src/x.py:Y",
        ci_evidence="run-123",
    )
    (result,) = verify_traceability((entry,))
    assert result.passed is False
    assert "task_id" in result.message


def test_verify_traceability_flags_entry_missing_test_id_as_failing() -> None:
    entry = TraceabilityEntry(
        req_id="REQ-2",
        ac_id="AC-2",
        task_id="TASK-2",
        test_id=None,
        code_ref=None,
        ci_evidence=None,
    )
    (result,) = verify_traceability((entry,))
    assert result.passed is False
    assert "test_id" in result.message


def test_verify_traceability_passes_fully_resolved_entry() -> None:
    entry = TraceabilityEntry(
        req_id="REQ-3",
        ac_id="AC-3",
        task_id="TASK-3",
        test_id="tests/test_x.py::test_z",
        code_ref="src/x.py:Z",
        ci_evidence="run-456",
    )
    (result,) = verify_traceability((entry,))
    assert result.passed is True


def test_verify_traceability_processes_multiple_entries_independently() -> None:
    good = TraceabilityEntry(
        req_id="REQ-4",
        ac_id="AC-4",
        task_id="TASK-4",
        test_id="tests/test_x.py::test_w",
        code_ref="src/x.py:W",
        ci_evidence="run-789",
    )
    bad = TraceabilityEntry(
        req_id="REQ-5",
        ac_id="AC-5",
        task_id=None,
        test_id=None,
        code_ref=None,
        ci_evidence=None,
    )
    results = verify_traceability((good, bad))
    assert len(results) == 2
    assert results[0].passed is True
    assert results[1].passed is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src uv run pytest tests/workflow/test_traceability.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ooagent.workflow.traceability'`

- [ ] **Step 3: Write the implementation**

Create `src/ooagent/workflow/traceability.py`:

```python
"""ooagent/workflow/traceability.py — §6 bidirectional traceability matrix validation.

An entry is an orphan (§6 CLAUDE.md-equivalent, docs/SPECDRIVEN.md §6) when
it lacks a task_id or a test_id — code without a requirement, or a
requirement without a test, is a defect.
"""

from __future__ import annotations

from ooagent.core.protocols import GateResult, TraceabilityEntry


def verify_traceability(
    entries: tuple[TraceabilityEntry, ...],
) -> tuple[GateResult, ...]:
    results: list[GateResult] = []
    for entry in entries:
        missing = [
            field_name
            for field_name, value in (
                ("task_id", entry.task_id),
                ("test_id", entry.test_id),
            )
            if value is None
        ]
        if missing:
            results.append(
                GateResult(
                    gate_name="verify-spec",
                    passed=False,
                    message=(
                        f"{entry.req_id}/{entry.ac_id} is an orphan: missing "
                        f"{', '.join(missing)}"
                    ),
                )
            )
        else:
            results.append(
                GateResult(
                    gate_name="verify-spec",
                    passed=True,
                    message=f"{entry.req_id}/{entry.ac_id} resolves end-to-end",
                )
            )
    return tuple(results)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/workflow/test_traceability.py -v`
Expected: PASS

- [ ] **Step 5: Type-check and commit**

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check`
Expected: mypy reports `Success: no issues found`; ruff check and format --check both report no findings (empty output, exit 0)

```bash
git add src/ooagent/workflow/traceability.py tests/workflow/test_traceability.py
git commit -m "feat(workflow): add traceability-matrix orphan detection"
```

---

### Task 5: `workflow/spec_driven.py` — `SpecDrivenWorkflow` + barrel export

**Files:**
- Create: `src/ooagent/workflow/spec_driven.py`
- Modify: `src/ooagent/workflow/__init__.py` (replace the Task 2 placeholder body with real exports)
- Test: `tests/workflow/test_spec_driven_workflow.py`

**Interfaces:**
- Consumes: `IDeliveryWorkflow`, `Phase`, `Article`, `GateSpec`, `GateResult`, `TraceabilityEntry` (Task 1); `ARTICLES` (Task 2); `GATE_TARGETS` (Task 3); `verify_traceability` (Task 4).
- Produces: `PHASES: tuple[Phase, ...]` and `SpecDrivenWorkflow` (concrete `IDeliveryWorkflow`) — consumed by Task 6's conformance suite, Task 8's self-hosting example, and `ooagent.workflow` barrel imports.

- [ ] **Step 1: Write the failing test**

Create `tests/workflow/test_spec_driven_workflow.py`:

```python
"""tests/workflow/test_spec_driven_workflow.py — SpecDrivenWorkflow unit tests."""

from __future__ import annotations

import pytest

from ooagent.core.protocols import TraceabilityEntry
from ooagent.workflow.spec_driven import SpecDrivenWorkflow

workflow = SpecDrivenWorkflow()


def test_name_and_version() -> None:
    assert workflow.name == "spec-driven"
    assert workflow.version == "2026.07.001"


def test_phases_has_eleven_entries_starting_with_constitution() -> None:
    phases = workflow.phases()
    assert len(phases) == 11
    assert phases[0].name == "/constitution"
    assert phases[-1].name == "/support"


def test_gate_chain_order_matches_section_three() -> None:
    expected = (
        "g_form",
        "g_security",
        "g_governance",
        "g_lifecycle",
        "g_traceability",
        "g_correctness",
    )
    assert workflow.gate_chain("/specify") == expected


def test_gate_chain_is_the_same_for_every_valid_phase() -> None:
    chains = {workflow.gate_chain(p.name) for p in workflow.phases()}
    assert len(chains) == 1


def test_gate_chain_raises_value_error_for_unknown_phase() -> None:
    with pytest.raises(ValueError):
        workflow.gate_chain("/not-a-real-phase")


def test_constitution_and_gate_targets_delegate_to_their_modules() -> None:
    assert len(workflow.constitution()) == 8
    assert len(workflow.gate_targets()) == 19


def test_verify_traceability_delegates_to_traceability_module() -> None:
    entry = TraceabilityEntry(
        req_id="REQ-1",
        ac_id="AC-1",
        task_id="TASK-1",
        test_id="tests/test_x.py::test_y",
        code_ref="src/x.py:Y",
        ci_evidence="run-1",
    )
    (result,) = workflow.verify_traceability((entry,))
    assert result.passed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src uv run pytest tests/workflow/test_spec_driven_workflow.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ooagent.workflow.spec_driven'`

- [ ] **Step 3: Write the implementation**

Create `src/ooagent/workflow/spec_driven.py`:

```python
"""ooagent/workflow/spec_driven.py — SpecDrivenWorkflow(IDeliveryWorkflow).

The canonical methodology: GitHub Spec Kit SDD flow. See
docs/SPECDRIVEN.md for the full identity, bootstrap, and command
integration description this class implements.
"""

from __future__ import annotations

from ooagent.core.protocols import (
    Article,
    GateResult,
    GateSpec,
    IDeliveryWorkflow,
    Phase,
    TraceabilityEntry,
)
from ooagent.workflow.constitution import ARTICLES
from ooagent.workflow.gate_catalog import GATE_TARGETS
from ooagent.workflow.traceability import verify_traceability as _verify_traceability_entries

PHASES: tuple[Phase, ...] = (
    Phase(
        name="/constitution",
        artifact="constitution.md",
        itil_stage="(baseline)",
        cobit_domain="EDM",
        owasp_gate="A06 threat baseline",
        oop_pattern="invariants",
    ),
    Phase(
        name="/specify",
        artifact="spec.md",
        itil_stage="Engage",
        cobit_domain="APO",
        owasp_gate="abuse-cases noted",
        oop_pattern="-",
    ),
    Phase(
        name="/clarify",
        artifact="spec.md (revised)",
        itil_stage="Engage",
        cobit_domain="APO",
        owasp_gate="ambiguity = risk",
        oop_pattern="Protected Variations",
    ),
    Phase(
        name="/plan",
        artifact="plan.md",
        itil_stage="Design&Transition",
        cobit_domain="BAI",
        owasp_gate="/threat-model, ASVS",
        oop_pattern="DIP stack + gate inject",
    ),
    Phase(
        name="/checklist",
        artifact="checklist.md",
        itil_stage="Design&Transition",
        cobit_domain="MEA",
        owasp_gate="security checklist",
        oop_pattern="self-check",
    ),
    Phase(
        name="/tasks",
        artifact="tasks.md",
        itil_stage="Build (prep)",
        cobit_domain="BAI",
        owasp_gate="security task/story",
        oop_pattern="Command (reified [P])",
    ),
    Phase(
        name="/analyze",
        artifact="analysis (read-only)",
        itil_stage="(gate)",
        cobit_domain="MEA",
        owasp_gate="sec-req coverage",
        oop_pattern="Chain of Responsibility",
    ),
    Phase(
        name="/implement",
        artifact="code + tests",
        itil_stage="Build",
        cobit_domain="BAI",
        owasp_gate="A01-A10 by default",
        oop_pattern="all",
    ),
    Phase(
        name="/verify",
        artifact="ci evidence",
        itil_stage="Design->Deliver",
        cobit_domain="MEA",
        owasp_gate="gate-contract run",
        oop_pattern="-",
    ),
    Phase(
        name="/handoff",
        artifact="handoff pack",
        itil_stage="Transition(release)",
        cobit_domain="EDM",
        owasp_gate="logging/alerting xfer",
        oop_pattern="-",
    ),
    Phase(
        name="/support",
        artifact="change records",
        itil_stage="Deliver&Support",
        cobit_domain="DSS",
        owasp_gate="incident->problem",
        oop_pattern="-",
    ),
)

_EXIT_GATE_CHAIN: tuple[str, ...] = (
    "g_form",
    "g_security",
    "g_governance",
    "g_lifecycle",
    "g_traceability",
    "g_correctness",
)


class SpecDrivenWorkflow(IDeliveryWorkflow):
    """Concrete IDeliveryWorkflow: GitHub Spec Kit-style SDD methodology."""

    @property
    def name(self) -> str:
        return "spec-driven"

    @property
    def version(self) -> str:
        return "2026.07.001"

    def phases(self) -> tuple[Phase, ...]:
        return PHASES

    def constitution(self) -> tuple[Article, ...]:
        return ARTICLES

    def gate_targets(self) -> dict[str, GateSpec]:
        return GATE_TARGETS

    def gate_chain(self, phase_name: str) -> tuple[str, ...]:
        if phase_name not in {p.name for p in PHASES}:
            raise ValueError(f"unknown phase: {phase_name!r}")
        return _EXIT_GATE_CHAIN

    def verify_traceability(
        self, entries: tuple[TraceabilityEntry, ...]
    ) -> tuple[GateResult, ...]:
        return _verify_traceability_entries(entries)
```

Replace the body of `src/ooagent/workflow/__init__.py` (from Task 2's placeholder) with:

```python
"""ooagent/workflow/__init__.py — barrel export for the SpecDrivenWorkflow (SDD) layer."""

from __future__ import annotations

from ooagent.workflow.constitution import ARTICLES
from ooagent.workflow.gate_catalog import GATE_TARGETS
from ooagent.workflow.spec_driven import PHASES, SpecDrivenWorkflow
from ooagent.workflow.traceability import verify_traceability

__all__ = [
    "ARTICLES",
    "GATE_TARGETS",
    "PHASES",
    "SpecDrivenWorkflow",
    "verify_traceability",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/workflow/ -v`
Expected: PASS (all of `tests/workflow/`, old and new)

- [ ] **Step 5: Type-check and commit**

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check`
Expected: mypy reports `Success: no issues found`; ruff check and format --check both report no findings (empty output, exit 0)

```bash
git add src/ooagent/workflow/spec_driven.py src/ooagent/workflow/__init__.py tests/workflow/test_spec_driven_workflow.py
git commit -m "feat(workflow): add SpecDrivenWorkflow — the 11-phase concrete IDeliveryWorkflow"
```

---

### Task 6: `IDeliveryWorkflow` conformance suite

**Files:**
- Create: `tests/conformance/test_delivery_workflow.py`

**Interfaces:**
- Consumes: `IDeliveryWorkflow` (Task 1), `SpecDrivenWorkflow` (Task 5).
- Produces: nothing new — this is a leaf test file.

- [ ] **Step 1: Write the test**

Create `tests/conformance/test_delivery_workflow.py`:

```python
"""tests/conformance/test_delivery_workflow.py — IDeliveryWorkflow conformance suite (§17 CLAUDE.md)."""

from __future__ import annotations

from ooagent.core.protocols import IDeliveryWorkflow
from ooagent.workflow.spec_driven import SpecDrivenWorkflow

workflow: IDeliveryWorkflow = SpecDrivenWorkflow()


def test_phases_returns_non_empty_tuple() -> None:
    phases = workflow.phases()
    assert len(phases) > 0, "phases() must return a non-empty tuple"


def test_constitution_returns_exactly_eight_articles() -> None:
    articles = workflow.constitution()
    assert len(articles) == 8, "constitution() must return exactly 8 Articles"


def test_gate_targets_returns_exactly_nineteen_gate_specs() -> None:
    targets = workflow.gate_targets()
    assert len(targets) == 19, "gate_targets() must return exactly 19 GateSpec entries"


def test_verify_traceability_on_empty_tuple_does_not_raise() -> None:
    result = workflow.verify_traceability(())
    assert result == (), "verify_traceability(()) must return an empty tuple, not raise"
```

This suite runs as part of `ci-core.yml`'s existing "Run conformance tests" step (`PYTHONPATH=src uv run pytest tests/conformance/ -v`) with zero changes to that workflow — it already runs every file under `tests/conformance/`.

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/conformance/test_delivery_workflow.py -v`
Expected: PASS

- [ ] **Step 3: Run the full conformance suite to confirm no regression**

Run: `PYTHONPATH=src uv run pytest tests/conformance/ -v`
Expected: all conformance tests PASS (existing `IAgent`/`IDomainContext`/`ITool`/`ILLMClient` suites plus the new one)

- [ ] **Step 4: Commit**

```bash
git add tests/conformance/test_delivery_workflow.py
git commit -m "test(workflow): add IDeliveryWorkflow conformance suite"
```

---

### Task 7: `.specify/` scaffold — constitution, templates, gate Makefile

**Files:**
- Create: `.specify/memory/constitution.md`
- Create: `.specify/templates/spec.md`
- Create: `.specify/templates/plan.md`
- Create: `.specify/templates/tasks.md`
- Create: `.specify/templates/checklist.md`
- Create: `.specify/gates/Makefile`
- Create: `.specify/ci/out/.gitkeep`
- Create: `.specify/ledger/audit.log`
- Modify: `pyproject.toml` (add `pytest-cov` to the `dev` optional-dependencies group)
- Test: `tests/workflow/test_gate_makefile.py`

**Interfaces:**
- Consumes: `GATE_TARGETS` from `ooagent.workflow.gate_catalog` (Task 3) — the test cross-checks every catalog key has a Makefile recipe.
- Produces: a runnable `.specify/gates/Makefile` — consumed by Task 9's `sdd-gate.yml` (`make -f .specify/gates/Makefile <target>`) and Task 8's `verify-spec` target (which calls `scripts/sdd-verify-spec.sh`, created in Task 8).

- [ ] **Step 1: Add `pytest-cov` to `pyproject.toml`**

In `pyproject.toml`, change the `dev` optional-dependencies group from:

```toml
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "mypy>=1.11",
    "ruff>=0.6",
]
```

to:

```toml
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "mypy>=1.11",
    "ruff>=0.6",
]
```

Run: `uv sync --extra dev --extra otel`
Expected: `pytest-cov` installed into `.venv`, no errors.

- [ ] **Step 2: Write the failing test**

Create `tests/workflow/test_gate_makefile.py`:

```python
"""tests/workflow/test_gate_makefile.py — .specify/gates/Makefile structural check.

`make` is not installed in every dev environment, so this test checks
Makefile *structure* (every catalog gate has a recipe target) rather than
executing it. Real end-to-end execution happens in CI
(.github/workflows/sdd-gate.yml, ubuntu-latest has make preinstalled).
"""

from __future__ import annotations

from pathlib import Path

from ooagent.workflow.gate_catalog import GATE_TARGETS

MAKEFILE_PATH = Path(__file__).resolve().parents[2] / ".specify" / "gates" / "Makefile"


def test_makefile_exists() -> None:
    assert MAKEFILE_PATH.is_file(), f"expected {MAKEFILE_PATH} to exist"


def test_makefile_defines_every_catalog_gate_target() -> None:
    text = MAKEFILE_PATH.read_text(encoding="utf-8")
    for name in GATE_TARGETS:
        marker = f"\n{name}:"
        assert marker in text, f"Makefile is missing a recipe for gate target {name!r}"


def test_makefile_required_gates_have_non_optional_recipes() -> None:
    text = MAKEFILE_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    for name, spec in GATE_TARGETS.items():
        if not spec.required:
            continue
        idx = next(i for i, line in enumerate(lines) if line.startswith(f"{name}:"))
        recipe_lines = []
        for line in lines[idx + 1 :]:
            if not line.startswith("\t"):
                break
            recipe_lines.append(line)
        recipe_text = "\n".join(recipe_lines)
        assert "_optional" not in recipe_text, (
            f"required gate {name!r} must not use the _optional skip helper"
        )
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=src uv run pytest tests/workflow/test_gate_makefile.py -v`
Expected: FAIL — `test_makefile_exists` fails (`.specify/gates/Makefile` does not exist yet)

- [ ] **Step 4: Create the constitution and templates**

Create `.specify/memory/constitution.md`:

```markdown
# OOAgent — SDD Constitution

> Instantiated via `SpecDrivenWorkflow` (`src/ooagent/workflow/spec_driven.py`).
> Machine-readable source of truth: `src/ooagent/workflow/constitution.py`.
> This file is the human-readable projection; keep both in sync.

## ARTICLE I — Form

Artifact-first, typed, no filler, source-tagged. Every numeric claim
carries a unit and a SourceTag (measured/assumed/cited/derived), per
CLAUDE.md §15 Output Discipline.

## ARTICLE II — Security

Secure-by-default; OWASP baseline enforced by the existing AI Safety Gate
(13 guards), gitleaks secret scanning, and pip-audit dependency auditing.
Gates block, they do not warn.

## ARTICLE III — Governance

Client Accountable / engineer Responsible; every gate run is
ledger-audited in `.specify/ledger/audit.log`.

## ARTICLE IV — Lifecycle

Gitflow (`develop` -> `release`/`hotfix` -> `master`) is the
change-controlled lifecycle; every merge is a change record.

## ARTICLE V — Architecture

SOLID/GRASP/GoF as codified in CLAUDE.md §§2-4; patterns reified as real
objects, not comments. Default algorithmic complexity <= O(n); annotate
deviations.

## ARTICLE VI — Testing (NON-NEGOTIABLE)

TDD: no implementation code before an approved failing test (Red),
matching this repo's subagent-driven-development practice.

## ARTICLE VII — Zero Defects

Every requirement is testable; defect-escape-rate target is zero.
Coverage floor: **70%** (`pytest --cov-fail-under=70`), ratchets upward
only, never down.

## ARTICLE VIII — Traceability

spec -> task -> code -> test -> CI evidence, bidirectional, source-tagged.
Orphans (code without a requirement, or a requirement without a test) are
defects.
```

Create `.specify/templates/spec.md`:

```markdown
# <NNN> — <Feature Title>

## Requirements

<!-- One REQ-id per testable requirement. -->

- **REQ-1**: <requirement text>
  - **AC-1**: <acceptance criterion — must be objectively verifiable>

## User Stories

<!-- Who wants this and why. -->

## Success Criteria

<!-- How we know REQ-* are satisfied. -->

## Edge Cases & Abuse Cases

<!-- ARTICLE II — what could go wrong, who might misuse this. -->

## Out of Scope

<!-- Explicitly excluded, so it isn't mistaken for an oversight. -->
```

Create `.specify/templates/plan.md`:

```markdown
# <NNN> — Plan

## Stack (DIP injection point)

<!-- Concrete languages/frameworks/tools for THIS feature. -->

## Architecture

<!-- Components, data flow, patterns used (cite CLAUDE.md §§1-4). -->

## Constitution Check

<!-- One line per Article: how this plan satisfies it, or N/A + why. -->

## Gate Recipes Touched

<!-- Which .specify/gates/Makefile targets this feature exercises. -->
```

Create `.specify/templates/tasks.md`:

```markdown
# <NNN> — Tasks

<!-- One row per TASK-id. [P] marks tasks that can run in parallel. -->

- [ ] **TASK-1** [P] <task description> — file: `<path>` — implements REQ-1/AC-1
  - **TEST-1**: `<test file>::<test function>` (must FAIL before TASK-1's code exists)
```

Create `.specify/templates/checklist.md`:

```markdown
# <NNN> — Quality & Security Checklist

<!-- Derived from constitution.md; one line per applicable Article. -->

- [ ] ARTICLE I — Form: source-tagged, typed, no filler
- [ ] ARTICLE II — Security: OWASP baseline reviewed for this feature
- [ ] ARTICLE III — Governance: RACI clear, ledger entry planned
- [ ] ARTICLE IV — Lifecycle: branch/merge strategy declared
- [ ] ARTICLE V — Architecture: patterns cited, complexity annotated
- [ ] ARTICLE VI — Testing: failing tests written before implementation
- [ ] ARTICLE VII — Zero Defects: every REQ has >=1 AC and >=1 TEST
- [ ] ARTICLE VIII — Traceability: REQ/AC/TASK/TEST/CODE/CI links resolved
```

- [ ] **Step 5: Create the gate Makefile**

Create `.specify/gates/Makefile`:

```makefile
# .specify/gates/Makefile
# SpecDrivenWorkflow §5 — gate contract (DIP seam) for OOAgent itself.
# .github/workflows/sdd-gate.yml calls these targets by NAME. Recipes below
# are THIS repo's concrete bindings (uv/mypy/ruff/pytest/pip-audit/gitleaks).
# Contract: a gate target exits 0 on pass, non-zero on fail.

SHELL := /bin/sh
EVIDENCE := .specify/ci/out
LEDGER := .specify/ledger/audit.log

# _optional NAME : a conditional gate genuinely not applicable to this
# project (library, no DB/artifact-signing/UI/deploy pipeline) — skip
# with a logged reason (exit 0), per the SDD template's fail-open design
# for if-* gates whose recipe is not yet implemented.
define _optional
@echo "::notice::optional gate '$(1)' not applicable to this project — skipped"; exit 0
endef

.PHONY: help \
  verify-spec typecheck lint format-check \
  sast sca secret-scan \
  migrate test coverage-gate \
  build sign e2e \
  verify-signature deploy smoke dast alerting-probe \
  ledger

help:
	@grep -E '^[a-z-]+:' $(firstword $(MAKEFILE_LIST)) | sed 's/:.*//' | sort

# ── REQUIRED gates ────────────────────────────────────────────────────────
verify-spec:        ## SDD artifacts present + traceability resolved (§6)
	bash scripts/sdd-verify-spec.sh

typecheck:          ## static type verification
	uv run mypy --strict

lint:               ## linter, zero warnings
	uv run ruff check

format-check:       ## formatter in check mode
	uv run ruff format --check

sast:               ## static security analysis (AI Safety Gate, 13 guards)
	bash scripts/ai-safety-gate.sh --verbose

sca:                ## dependency scan (A03)
	uv run --with pip-audit pip-audit

# secret-scan detects committed secrets. CI runs the dedicated gitleaks
# GitHub Action (.github/workflows/ci-core.yml); locally this recipe uses
# the gitleaks CLI if present, and otherwise skips with a pointer to CI.
secret-scan:        ## secret detection (A02)
	@command -v gitleaks >/dev/null 2>&1 && gitleaks detect --no-git -v || echo "::notice::gitleaks not installed locally — enforced in CI (ci-core.yml)"

test:               ## unit + integration + contract; coverage → $(EVIDENCE)/
	@mkdir -p $(EVIDENCE)
	PYTHONPATH=src uv run pytest tests/ --cov=ooagent --cov-report=xml:$(EVIDENCE)/coverage.xml

coverage-gate:      ## fail below constitution threshold (ARTICLE VII: 70%)
	PYTHONPATH=src uv run pytest tests/ --cov=ooagent --cov-fail-under=70 -q

ledger:             ## append COBIT audit entry → $(LEDGER) (ARTICLE III)
	@mkdir -p $(dir $(LEDGER))
	@echo "$$(date -u +%Y-%m-%dT%H:%M:%SZ) commit=$$(git rev-parse HEAD) gates=verify-spec,typecheck,lint,format-check,sast,sca,secret-scan,test,coverage-gate" >> $(LEDGER)

# ── CONDITIONAL gates (genuinely N/A for this project — see design doc) ──
migrate:            ## apply schema migrations — no DB in this project
	$(call _optional,migrate)

build:              ## build deployable/distributable (already exercised by ci-core.yml)
	uv build

sign:               ## sign artifact + provenance (A08) — no signed artifact today
	$(call _optional,sign)

e2e:                ## end-to-end suite — no UI in this project
	$(call _optional,e2e)

verify-signature:   ## verify signature before deploy — no deploy pipeline
	$(call _optional,verify-signature)

deploy:             ## deploy, gated on all-green — no deploy pipeline
	$(call _optional,deploy)

smoke:              ## post-deploy health — no deploy pipeline
	$(call _optional,smoke)

dast:               ## dynamic security scan — no deploy pipeline
	$(call _optional,dast)

alerting-probe:     ## security logging/alerting reachable (A09) — no deploy pipeline
	$(call _optional,alerting-probe)
```

- [ ] **Step 6: Create the evidence directory placeholder and ledger seed**

Create `.specify/ci/out/.gitkeep`:

```
```

(empty file — keeps the otherwise-empty `ci/out/` directory tracked by git)

Create `.specify/ledger/audit.log`:

```
# COBIT audit ledger — append-only. See ARTICLE III (.specify/memory/constitution.md).
# Format: <UTC timestamp> commit=<sha> gates=<comma-separated gate names run>
```

- [ ] **Step 7: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/workflow/test_gate_makefile.py -v`
Expected: PASS

- [ ] **Step 8: Run the full test suite with coverage to confirm the 70% floor holds**

Run: `PYTHONPATH=src uv run pytest tests/ --cov=ooagent --cov-fail-under=70 -q`
Expected: PASS, total coverage >= 70%

- [ ] **Step 9: Type-check and commit**

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check`
Expected: mypy reports `Success: no issues found`; ruff check and format --check both report no findings (empty output, exit 0)

```bash
git add pyproject.toml .specify/ tests/workflow/test_gate_makefile.py
git commit -m "feat(workflow): add .specify/ scaffold — constitution, templates, gate Makefile"
```

---

### Task 8: Self-hosting example + `verify-spec` gate script

**Files:**
- Create: `specs/001-spec-driven-workflow-layer/spec.md`
- Create: `specs/001-spec-driven-workflow-layer/plan.md`
- Create: `specs/001-spec-driven-workflow-layer/tasks.md`
- Create: `scripts/sdd-verify-spec.sh`
- Test: `tests/workflow/test_sdd_verify_spec.py`

**Interfaces:**
- Consumes: nothing from earlier tasks directly (the script is standalone bash); the self-hosting `spec.md`/`tasks.md` content references file paths created by Tasks 1–7 as its `REQ`/`TASK`/`TEST` evidence.
- Produces: `scripts/sdd-verify-spec.sh` — consumed by Task 7's Makefile `verify-spec` target (already wired in Task 7 to call this script) and Task 9's `sdd-gate.yml`.

- [ ] **Step 1: Write the self-hosting spec, plan, and tasks documents**

Create `specs/001-spec-driven-workflow-layer/spec.md`:

```markdown
# 001 — SpecDrivenWorkflow / IDeliveryWorkflow Layer

## Requirements

- **REQ-1**: `IDeliveryWorkflow` and its value objects exist in `core/protocols.py`.
  - **AC-1**: `IDeliveryWorkflow` cannot be instantiated directly (raises `TypeError`); `Phase`/`Article`/`GateSpec`/`TraceabilityEntry`/`GateResult` are frozen dataclasses.
- **REQ-2**: `SpecDrivenWorkflow` provides exactly 8 constitution Articles.
  - **AC-2**: `constitution()` returns exactly 8 `Article` entries, numerals `I` through `VIII` in order.
- **REQ-3**: `SpecDrivenWorkflow` provides exactly 19 gate targets matching §5 of the design.
  - **AC-3**: `gate_targets()` returns exactly 19 `GateSpec` entries; the 9 conditional gates are not required.
- **REQ-4**: Traceability verification flags orphan entries as failing.
  - **AC-4**: `verify_traceability()` returns a failing `GateResult` for an entry missing `task_id` or `test_id`, and a passing `GateResult` for a fully-resolved entry.
- **REQ-5**: The `.specify/` scaffold provides a runnable, project-bound gate contract instead of blank stubs.
  - **AC-5**: `.specify/gates/Makefile` defines a recipe for every gate in the catalog; every *required* gate's recipe is a real command, not the `_optional` skip helper.
- **REQ-6**: The `verify-spec` gate blocks on missing or orphaned SDD artifacts.
  - **AC-6**: `scripts/sdd-verify-spec.sh` exits non-zero when a `specs/<slug>/` directory is missing an artifact or has an orphan `REQ`/`TASK`/`TEST`, and exits 0 when this very feature's `specs/001-spec-driven-workflow-layer/` is fully resolved.

## User Stories

As a maintainer of OOAgent (or a fork of it), I want a gate-enforced,
traceable delivery process for new features, so that every requirement
ships with proof (a test, a code reference, CI evidence) rather than
relying on review discipline alone.

## Success Criteria

All of REQ-1 through REQ-6 hold, verified by their paired tests (see
`tasks.md`), and `bash scripts/sdd-verify-spec.sh` exits 0 against this
very `specs/001-spec-driven-workflow-layer/` directory.

## Edge Cases & Abuse Cases

- A future spec directory ships `spec.md`/`plan.md` but forgets
  `tasks.md` — `verify-spec` must fail closed (missing-artifact check).
- A future spec references a `REQ-id` with no implementing task —
  `verify-spec` must flag it as an orphan requirement.
- A future `tasks.md` has more `TASK-*` entries than `TEST-*` entries
  (a task with no paired test) — `verify-spec` must fail on the count
  mismatch (ARTICLE VI).

## Out of Scope

A real slash-command CLI (`/specify`, `/plan`, ...) wired into an agent
harness; rewriting the existing 6 Gitflow workflows to call through the
Makefile; `sign`/`e2e`/`deploy`/`smoke`/`dast`/`verify-signature`/
`alerting-probe` gates (no deployable service exists for this library).
```

Create `specs/001-spec-driven-workflow-layer/plan.md`:

```markdown
# 001 — Plan

## Stack (DIP injection point)

Python 3.11, `uv`, `mypy --strict`, `ruff`, `pytest` + `pytest-cov` — this
repo's existing stack (`docs/superpowers/specs/2026-07-04-python-port-design.md`).
Bash for `scripts/sdd-verify-spec.sh`. GNU Make for `.specify/gates/Makefile`.

## Architecture

`IDeliveryWorkflow` (ABC, `core/protocols.py`) is a peer layer to
`IDomainContext` — never invoked from `core/agent.py`'s `respond()`.
`SpecDrivenWorkflow` (`workflow/spec_driven.py`) is the sole
implementation, composed from `workflow/constitution.py` (Article data),
`workflow/gate_catalog.py` (GateSpec data), and `workflow/traceability.py`
(orphan-detection logic — a pure function, Information Expert on
traceability rules). Gate *execution* is explicitly out of this class's
responsibility (`binding = "gate-contract"`): `.specify/gates/Makefile`
is the DIP seam, per CLAUDE.md §3/§9 Adapter and Bridge pattern framing.

## Constitution Check

- ARTICLE I (Form): all new dataclasses are typed, frozen, no filler.
- ARTICLE II (Security): no new attack surface — no network calls, no
  secrets handled; existing AI Safety Gate/gitleaks/pip-audit scan the
  new files same as any other source file.
- ARTICLE III (Governance): `.specify/ledger/audit.log` gets its first
  real entries once `sdd-gate.yml` (Task 9) runs on a push.
- ARTICLE IV (Lifecycle): built on a feature branch via
  subagent-driven-development, merged to `develop` via the same Gitflow
  process as the Python port.
- ARTICLE V (Architecture): Information Expert (traceability module
  owns orphan rules), Pure Fabrication (`gate_catalog`/`constitution`
  have no real-world object counterpart, exist for cohesion), Adapter/
  Bridge (Makefile as DIP seam between gate names and concrete tools).
- ARTICLE VI (Testing): every task in `tasks.md` below pairs one
  implementation file with one test file, test written first.
- ARTICLE VII (Zero Defects): `coverage-gate` set to 70% (current
  measured baseline: 71%); this feature's own tests keep it at or above.
- ARTICLE VIII (Traceability): this very document is REQ-6's evidence.

## Gate Recipes Touched

`verify-spec` (new), `coverage-gate` (new), `ledger` (new), plus
`typecheck`/`lint`/`format-check`/`test` (already existed via
`ci-core.yml`, now also reachable through the Makefile for DIP-seam
parity — see `.github/workflows/sdd-gate.yml`).
```

Create `specs/001-spec-driven-workflow-layer/tasks.md`:

```markdown
# 001 — Tasks

- [ ] **TASK-1** [P] Add `IDeliveryWorkflow` ABC and SDD value objects — file: `src/ooagent/core/protocols.py` — implements REQ-1/AC-1
  - **TEST-1**: `tests/core/test_protocols.py::test_idelivery_workflow_cannot_be_instantiated_directly`

- [ ] **TASK-2** [P] Add the 8-Article constitution — file: `src/ooagent/workflow/constitution.py` — implements REQ-2/AC-2
  - **TEST-2**: `tests/workflow/test_constitution.py::test_constitution_has_exactly_eight_articles`

- [ ] **TASK-3** [P] Add the 19-target gate catalog — file: `src/ooagent/workflow/gate_catalog.py` — implements REQ-3/AC-3
  - **TEST-3**: `tests/workflow/test_gate_catalog.py::test_gate_catalog_has_exactly_nineteen_targets`

- [ ] **TASK-4** [P] Add traceability orphan detection — file: `src/ooagent/workflow/traceability.py` — implements REQ-4/AC-4
  - **TEST-4**: `tests/workflow/test_traceability.py::test_verify_traceability_flags_entry_missing_task_id_as_failing`

- [ ] **TASK-5** Add the runnable gate Makefile — file: `.specify/gates/Makefile` — implements REQ-5/AC-5
  - **TEST-5**: `tests/workflow/test_gate_makefile.py::test_makefile_required_gates_have_non_optional_recipes`

- [ ] **TASK-6** Add the verify-spec traceability checker — file: `scripts/sdd-verify-spec.sh` — implements REQ-6/AC-6
  - **TEST-6**: `tests/workflow/test_sdd_verify_spec.py::test_script_passes_on_this_repos_own_specs_directory`
```

- [ ] **Step 2: Write the failing test**

Create `tests/workflow/test_sdd_verify_spec.py`:

```python
"""tests/workflow/test_sdd_verify_spec.py — scripts/sdd-verify-spec.sh behavior."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "sdd-verify-spec.sh"


def test_script_passes_on_this_repos_own_specs_directory() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_script_reports_orphan_req_with_no_matching_task(tmp_path: Path) -> None:
    specs_dir = tmp_path / "specs" / "999-orphan-example"
    specs_dir.mkdir(parents=True)
    (specs_dir / "spec.md").write_text(
        "- **REQ-1**: something\n  - **AC-1**: criterion\n", encoding="utf-8"
    )
    (specs_dir / "plan.md").write_text("# plan\n", encoding="utf-8")
    (specs_dir / "tasks.md").write_text(
        "- [ ] **TASK-1** does unrelated work\n  - **TEST-1**: `tests/test_x.py::test_y`\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "orphan" in result.stdout.lower()


def test_script_reports_missing_artifact(tmp_path: Path) -> None:
    specs_dir = tmp_path / "specs" / "998-missing-plan"
    specs_dir.mkdir(parents=True)
    (specs_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    (specs_dir / "tasks.md").write_text("# tasks\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "missing plan.md" in result.stdout.lower() or "missing plan.md" in result.stderr.lower()


def test_script_exits_zero_when_no_specs_directories_exist(tmp_path: Path) -> None:
    (tmp_path / "specs").mkdir()

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=src uv run pytest tests/workflow/test_sdd_verify_spec.py -v`
Expected: FAIL — `scripts/sdd-verify-spec.sh` does not exist, so `subprocess.run` raises `FileNotFoundError` (bash reports "No such file or directory"), causing every test to error.

- [ ] **Step 4: Write the implementation**

Create `scripts/sdd-verify-spec.sh`:

```bash
#!/usr/bin/env bash
# scripts/sdd-verify-spec.sh
# SpecDrivenWorkflow — the `verify-spec` gate (.specify/gates/Makefile).
# Every specs/<NNN-slug>/ must ship spec.md + plan.md + tasks.md; every
# REQ-id in spec.md must be referenced by a TASK in tasks.md ("implements
# REQ-N/AC-M"); every TASK-id must have a paired TEST-id (1:1 count).
set -eu

FAILURES=0
SPECS_DIR="specs"

if [ ! -d "$SPECS_DIR" ]; then
  echo "::notice::${SPECS_DIR}/ does not exist — nothing to verify"
  exit 0
fi

FEATURE_DIRS=$(find "$SPECS_DIR" -mindepth 1 -maxdepth 1 -type d | sort)

if [ -z "$FEATURE_DIRS" ]; then
  echo "::notice::no feature directories under ${SPECS_DIR}/ yet — nothing to verify"
  exit 0
fi

for dir in $FEATURE_DIRS; do
  echo "Checking ${dir}..."

  for artifact in spec.md plan.md tasks.md; do
    if [ ! -f "${dir}/${artifact}" ]; then
      echo "❌ ${dir} is missing ${artifact}"
      FAILURES=$((FAILURES + 1))
    fi
  done

  if [ ! -f "${dir}/spec.md" ] || [ ! -f "${dir}/tasks.md" ]; then
    continue
  fi

  REQ_IDS=$(grep -oE '\*\*REQ-[0-9]+\*\*' "${dir}/spec.md" | tr -d '*' | sort -u || true)

  for req_id in $REQ_IDS; do
    if ! grep -q "implements ${req_id}/" "${dir}/tasks.md"; then
      echo "❌ ${dir}/spec.md: ${req_id} is an orphan — no task in tasks.md implements it"
      FAILURES=$((FAILURES + 1))
    fi
  done

  TASK_COUNT=$(grep -cE '\*\*TASK-[0-9]+\*\*' "${dir}/tasks.md" || true)
  TEST_COUNT=$(grep -cE '\*\*TEST-[0-9]+\*\*' "${dir}/tasks.md" || true)

  if [ "$TASK_COUNT" -ne "$TEST_COUNT" ]; then
    echo "❌ ${dir}/tasks.md: ${TASK_COUNT} TASK entries but ${TEST_COUNT} TEST entries — every task needs a paired test (ARTICLE VI)"
    FAILURES=$((FAILURES + 1))
  fi
done

if [ "$FAILURES" -gt 0 ]; then
  echo "verify-spec FAILED: ${FAILURES} issue(s)"
  exit 1
fi

echo "✅ verify-spec passed — all specs/ traceability resolved"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/workflow/test_sdd_verify_spec.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 6: Run the script directly against this repo to see the real output**

Run: `bash scripts/sdd-verify-spec.sh`
Expected:
```
Checking specs/001-spec-driven-workflow-layer...
✅ verify-spec passed — all specs/ traceability resolved
```

- [ ] **Step 7: Run the full test suite with coverage to confirm the 70% floor still holds**

Run: `PYTHONPATH=src uv run pytest tests/ --cov=ooagent --cov-fail-under=70 -q`
Expected: PASS, total coverage >= 70%

- [ ] **Step 8: Commit**

```bash
git add specs/ scripts/sdd-verify-spec.sh tests/workflow/test_sdd_verify_spec.py
git commit -m "feat(workflow): self-host spec 001 + add verify-spec traceability gate script"
```

---

### Task 9: `.github/workflows/sdd-gate.yml` — additive CI gate

**Files:**
- Create: `.github/workflows/sdd-gate.yml`

**Interfaces:**
- Consumes: `.specify/gates/Makefile` (Task 7), which in turn calls `scripts/sdd-verify-spec.sh` (Task 8).
- Produces: nothing consumed by later tasks — this is CI-only, additive alongside the 6 existing Gitflow workflows.

- [ ] **Step 1: Create the workflow file**

Create `.github/workflows/sdd-gate.yml`:

```yaml
name: sdd-gate

# SpecDrivenWorkflow §5 — Zero-Defects gate contract for OOAgent itself.
# Additive alongside the existing Gitflow workflows (ci-core.yml, etc.);
# does not replace or modify them. Runs the new SDD-specific gates
# (verify-spec, coverage-gate, ledger) plus typecheck/lint/format-check/
# test through the .specify/gates/Makefile DIP seam, proving the seam
# agrees with ci-core.yml's direct tool invocations.

on:
  push:
    branches: [develop, master]
  pull_request:
    branches: [develop, master]

concurrency:
  group: sdd-gate-${{ github.ref }}
  cancel-in-progress: true

env:
  GATE: make -f .specify/gates/Makefile

jobs:
  verify-spec:
    name: SDD verify-spec (traceability)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: $GATE verify-spec

  static-via-makefile:
    name: typecheck + lint + format-check via Makefile (DIP-seam parity)
    needs: verify-spec
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup uv
        uses: astral-sh/setup-uv@v3
      - name: Install dependencies
        run: uv sync --extra dev --extra otel
      - run: $GATE typecheck
      - run: $GATE lint
      - run: $GATE format-check

  test-and-coverage:
    name: test + coverage-gate via Makefile
    needs: static-via-makefile
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup uv
        uses: astral-sh/setup-uv@v3
      - name: Install dependencies
        run: uv sync --extra dev --extra otel
      - run: $GATE test
      - run: $GATE coverage-gate
      - name: Upload coverage evidence
        if: always() && hashFiles('.specify/ci/out/**') != ''
        uses: actions/upload-artifact@v4
        with:
          name: sdd-coverage-evidence-${{ github.sha }}
          path: .specify/ci/out/
          retention-days: 30

  ledger:
    name: ledger (COBIT audit entry)
    needs: [verify-spec, static-via-makefile, test-and-coverage]
    if: always() && github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: $GATE ledger
```

- [ ] **Step 2: Validate YAML syntax locally**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/sdd-gate.yml'))" && echo "valid YAML"`
Expected: `valid YAML` (no exception)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/sdd-gate.yml
git commit -m "ci: add sdd-gate.yml — additive verify-spec/coverage-gate/ledger workflow"
```

Note: this workflow's real end-to-end behavior (including `make` availability) is verified once pushed to GitHub's `ubuntu-latest` runners — it cannot be dry-run locally in this Windows worktree (no `make` installed; see Global Constraints). The final whole-branch review and the merge-to-`develop` step (per `superpowers:finishing-a-development-branch`) is where CI actually exercises it — confirm it goes green there before considering this task done.

---

### Task 10: `docs/SPECDRIVEN.md` + `CLAUDE.md` §24

**Files:**
- Create: `docs/SPECDRIVEN.md`
- Modify: `CLAUDE.md` (insert new §24 before the closing italicized line; append after "## 23. Self-Description")

**Interfaces:**
- Consumes: nothing (documentation only, references classes/files from Tasks 1–9 by path).
- Produces: nothing consumed by other tasks — final documentation task.

- [ ] **Step 1: Create `docs/SPECDRIVEN.md`**

Create `docs/SPECDRIVEN.md`:

```markdown
# SpecDrivenWorkflow — IDeliveryWorkflow implementation

> Fourth OOC layer. Plugs into `OOAgent` (`CLAUDE.md`) orthogonally to
> `IDomainContext`. `IDomainContext` = what · `IDeliveryWorkflow` = in
> what order, with what proof. Project-agnostic: knows gate **names and
> order**, never a stack. Concretes are DIP-injected per project via
> `.specify/gates/Makefile`. Canonical methodology: GitHub Spec Kit SDD
> flow.

---

## 0. Identity

```python
class SpecDrivenWorkflow(IDeliveryWorkflow):
    name    = "spec-driven"
    version = "2026.07.001"    # CalVer YYYY.MM.NNN — independent of
                                # pyproject.toml's package version
                                # (CLAUDE.md §18 — impls version
                                # independently)
```

Implementation: `src/ooagent/workflow/spec_driven.py`.

---

## 0.1 Bootstrap status (this repo)

This repo is not greenfield — the scaffold below already exists,
instantiated for this exact codebase:

```
.specify/
  memory/constitution.md            # the 8 Articles, this repo's bindings
  templates/{spec,plan,tasks,checklist}.md
  gates/Makefile                    # filled — uv/mypy/ruff/pytest/pip-audit/gitleaks
  ci/out/                           # gate evidence (coverage.xml) by convention
  ledger/audit.log                  # COBIT audit trail (ARTICLE III)
specs/                              # per-feature: <NNN-slug>/{spec,plan,tasks}.md
.github/workflows/sdd-gate.yml      # additive CI orchestrator
```

A downstream fork starting from scratch instead blanks
`constitution.md`'s bindings and `gates/Makefile`'s recipes until its own
`/plan`-equivalent phase fills them in — the structure and gate *names*
are what transfer verbatim; the concrete commands are per-project.

---

## 1. The Constitution

`.specify/memory/constitution.md` (human-readable) and
`src/ooagent/workflow/constitution.py` (`ARTICLES`, machine-readable) are
kept in sync. Every downstream phase validates against it:

```
ARTICLE I    — Form            : artifact-first, typed, no filler, source-tagged.
ARTICLE II   — Security        : OWASP baseline; AI Safety Gate + gitleaks + pip-audit block, not warn.
ARTICLE III  — Governance      : client Accountable / engineer Responsible; ledger-audited.
ARTICLE IV   — Lifecycle       : Gitflow is the change-controlled lifecycle.
ARTICLE V    — Architecture    : SOLID/GRASP/GoF (CLAUDE.md §§2-4); patterns reified.
ARTICLE VI   — Testing         : TDD, NON-NEGOTIABLE.
ARTICLE VII  — Zero Defects    : coverage floor 70%, ratchets up only.
ARTICLE VIII — Traceability    : spec → task → code → test → CI evidence, bidirectional.
```

Amending the constitution is a logged decision — edit both
`constitution.md` and `constitution.py` together, in the same commit.

---

## 2. Phase Pipeline (11 phases; Template Method skeleton)

```
# phase          artifact               ITIL                COBIT  OWASP gate            OOP
/constitution     constitution.md        (baseline)          EDM    A06 threat baseline   invariants
/specify          spec.md                Engage              APO    abuse-cases noted     —
/clarify          spec.md (revised)      Engage              APO    ambiguity = risk      Protected Variations
/plan             plan.md                Design&Transition   BAI    /threat-model, ASVS   DIP stack + gate inject
/checklist        checklist.md           Design&Transition   MEA    security checklist    self-check
/tasks            tasks.md               Build (prep)        BAI    security task/story   Command (reified [P])
/analyze          analysis (read-only)   (gate)              MEA    sec-req coverage      Chain of Responsibility
/implement        code + tests           Build               BAI    A01–A10 by default    all
/verify (CI/CD)   ci evidence            Design→Deliver      MEA    gate-contract run     —
/handoff          handoff pack           Transition(release) EDM    logging/alerting xfer —
/support          change records         Deliver&Support     DSS    incident→problem      —
```

Source: `PHASES` in `src/ooagent/workflow/spec_driven.py`.

---

## 3. Gate Chain (per phase, exit gates only — entry is "predecessor exists")

```
g_form          ARTICLE I satisfied?             → strip/rewrite
g_security      ARTICLE II OWASP baseline met?    → harden, re-enter
g_governance    ARTICLE III RACI + source-tags?   → annotate + ledger
g_lifecycle     ARTICLE IV stage declared?        → declare
g_traceability  ARTICLE VIII links resolved?      → backfill matrix
g_correctness   requirement/AC actually met?      → correct (final authority)
```

Precedence: **correctness ⊐ security ⊐ governance ⊐ lifecycle ⊐ form**.
Same chain for every phase — `SpecDrivenWorkflow.gate_chain(phase_name)`
returns this tuple regardless of which valid phase name is passed.

---

## 4. Zero Defects contract

```
defect class      owning prevention gate
  spec defect       → /clarify + /analyze
  design defect     → /plan
  contract defect   → /checklist
  code defect       → TDD Red→Green + typecheck + lint (ARTICLE VI)
  security defect   → sast/sca/secret-scan (ARTICLE II)
  regression        → full suite per change (ARTICLE VIII)

invariants:
  - Every spec requirement carries >=1 testable acceptance criterion.
  - No implementation precedes its failing test.
  - Requirement→test coverage = 100%; line coverage >= 70% (ratchets up).
  - All CI gates BLOCKING. No skip/continue-on-error on required gates.
  - Definition of Done = all exit gates green + CI green + ledger entry.
```

---

## 5. Gate Contract — concrete bindings for this repo

| gate target | required? | this repo's binding |
|---|---|---|
| verify-spec | yes | `scripts/sdd-verify-spec.sh` |
| typecheck | yes | `uv run mypy --strict` |
| lint | yes | `uv run ruff check` |
| format-check | yes | `uv run ruff format --check` |
| sast | yes | `scripts/ai-safety-gate.sh` |
| sca | yes | `pip-audit` |
| secret-scan | yes | `gitleaks` |
| migrate | no | N/A — no DB |
| test | yes | `pytest tests/` |
| coverage-gate | yes | `pytest --cov-fail-under=70` |
| build | no | `uv build` (enabled — real recipe) |
| sign | no | N/A — no signed artifact |
| e2e | no | N/A — no UI |
| verify-signature | no | N/A — no deploy pipeline |
| deploy | no | N/A |
| smoke | no | N/A |
| dast | no | N/A |
| alerting-probe | no | N/A |
| ledger | yes | append to `.specify/ledger/audit.log` |

Source: `GATE_TARGETS` in `src/ooagent/workflow/gate_catalog.py`;
recipes in `.specify/gates/Makefile`.

---

## 6. Traceability Matrix

```
REQ-id (spec.md) ─┬─ AC-id (acceptance criterion)
                  ├─ TASK-id (tasks.md, [P]?, file path)
                  ├─ TEST-id (test::case)  ← must FAIL before impl
                  ├─ CODE-ref (file:symbol)
                  └─ CI-evidence (run id, gate results, coverage)
```

Every row resolves end-to-end or `verify-spec` blocks. Orphan detection:
`verify_traceability()` in `src/ooagent/workflow/traceability.py`. Live
example: `specs/001-spec-driven-workflow-layer/`.

---

## 7. Command Integration (documentation only — no CLI wiring in this pass)

```
/init           → scaffold §0.1 structure for a downstream fork (this repo already has it).
/constitution   → project the constitution into constitution.md + constitution.py.
/specify        → spec.md: what & why, REQ/AC ids, edge/abuse cases. No stack.
/clarify        → resolve ambiguity; updates spec.md.
/plan           → plan.md: DIP stack + architecture + constitution-check.
/checklist      → quality + security checklist derived from constitution.
/tasks          → tasks.md: dependency-ordered, [P] markers, test-first.
/analyze        → read-only cross-artifact consistency check. Pre-implement gate.
/implement      → execute tasks under TDD; ledgered.
/verify         → run the §5 gate contract (.specify/gates/Makefile via CI).
/handoff        → README/scope-closure/RACI/change-enablement.
/support        → change records.
```

A real slash-command surface (wiring these into an agent harness) is a
future extension point — see §9 below, and CLAUDE.md §22's extension
protocol for the pattern to follow.

---

## 8. Composition with `OOAgent`

- `IDeliveryWorkflow` is a peer layer, not a `respond()` pipeline step —
  `core/agent.py` is untouched by this layer.
- An agent whose job *is* software delivery (e.g., a coding-assistant
  built on `OOAgent`) could compose `SpecDrivenWorkflow` as a collaborator
  the same way `ContextRegistry` holds an `IDomainContext` — that
  composition is left to the composing project, not prescribed here.
- Stack bindings live in `.specify/gates/Makefile` (DIP), never in
  `workflow/spec_driven.py`.
- On conflict between this layer and `IDomainContext` invariants,
  `CLAUDE.md`'s correctness-first precedence (§11) applies unchanged.

---

## 9. Anti-Patterns (forbidden — extends CLAUDE.md §21)

- Hardcoding any stack, tool, or vendor into `workflow/` or
  `sdd-gate.yml` (belongs in `.specify/gates/Makefile`).
- Implementing before `spec.md`/`plan.md`/`tasks.md` exist for a feature.
- Writing implementation code before its failing test (ARTICLE VI breach).
- `continue-on-error`/skip on any required gate.
- Merging with a red gate, an orphan requirement, or an untested
  acceptance criterion.
- Treating `verify-spec` findings as advisory rather than blocking.
- Invoking `IDeliveryWorkflow` methods from inside `core/agent.py`'s
  `respond()` — it is a peer layer, not a pipeline step.

---

## 10. Extension Points

To add a second `IDeliveryWorkflow` implementation (e.g. a lighter-weight
methodology for spikes): implement the ABC in a new
`src/ooagent/workflow/<name>.py`, ship its own conformance coverage
(mirror `tests/conformance/test_delivery_workflow.py` against the new
class), and register it wherever the composing project selects a
workflow — no edits to `core/protocols.py` required (OCP, per CLAUDE.md
§22's extension protocol).

---

## 11. Known Limitations

- No CLI/slash-command wiring in this pass — phases are documented and
  gate-checked, not yet invocable as literal commands.
- `sign`/`e2e`/`deploy`/`smoke`/`dast`/`verify-signature`/
  `alerting-probe` gates have `_optional` skip recipes, not real
  implementations — this project has no deployable service.
- `.specify/gates/Makefile` requires GNU Make; not verified locally on
  Windows dev environments without Make installed — verified in CI
  (`ubuntu-latest`) via `sdd-gate.yml`.
```

- [ ] **Step 2: Add CLAUDE.md §24**

In `CLAUDE.md`, find this exact text (the end of §23 Self-Description,
immediately before the closing italicized paragraph):

```
When asked what model is active:

> Report `ILLMClient.modelId`, e.g. `claude-opus-4-6`, `gpt-4o`, `llama3.3`.

---

*This document is the architectural ground truth for all OOAgent instances.
It is version-controlled, public, and MIT-licensed. Contributions welcome.*
```

Replace it with:

```
When asked what model is active:

> Report `ILLMClient.modelId`, e.g. `claude-opus-4-6`, `gpt-4o`, `llama3.3`.

---

## 24. IDeliveryWorkflow — SpecDrivenWorkflow Layer

A fourth OOC layer, orthogonal to `IDomainContext`: `IDeliveryWorkflow`
governs software-delivery *sequence and proof* — in what order features
get built, and what evidence proves each requirement is met — rather
than runtime query answering. `core/agent.py`'s `respond()` Template
Method is untouched; this layer is a peer, never a pipeline step.

The sole implementation, `SpecDrivenWorkflow`
(`src/ooagent/workflow/spec_driven.py`), reifies GitHub Spec Kit's
11-phase SDD methodology as real objects: an 8-Article constitution
(`workflow/constitution.py`), a 19-target gate catalog
(`workflow/gate_catalog.py`), and traceability-matrix orphan detection
(`workflow/traceability.py`). Gate *execution* is deliberately not this
class's concern — `.specify/gates/Makefile` is the DIP seam that binds
gate names to this repo's concrete tools (`mypy`, `ruff`, `pytest`,
`pip-audit`, `gitleaks`), enforced additively by
`.github/workflows/sdd-gate.yml` alongside the existing Gitflow
workflows.

Full specification: `docs/SPECDRIVEN.md`. Self-hosted proof of the
traceability gate: `specs/001-spec-driven-workflow-layer/`. Extension
protocol for adding a second `IDeliveryWorkflow` implementation follows
§22's pattern above — implement the ABC, ship conformance coverage, no
edits to `core/protocols.py` required.

---

*This document is the architectural ground truth for all OOAgent instances.
It is version-controlled, public, and MIT-licensed. Contributions welcome.*
```

- [ ] **Step 3: Run the full verification suite**

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check && PYTHONPATH=src uv run pytest tests/ --cov=ooagent --cov-fail-under=70 -q && bash scripts/sdd-verify-spec.sh`
Expected: all pass — 0 mypy errors, 0 ruff findings, full test suite green, coverage >= 70%, `verify-spec` passes.

- [ ] **Step 4: Commit**

```bash
git add docs/SPECDRIVEN.md CLAUDE.md
git commit -m "docs: add SPECDRIVEN.md and CLAUDE.md §24 for the IDeliveryWorkflow layer"
```

---

## Final Verification (before finishing-a-development-branch)

After Task 10, confirm the whole branch is coherent:

```bash
uv run mypy --strict
uv run ruff check
uv run ruff format --check
PYTHONPATH=src uv run pytest tests/ --cov=ooagent --cov-report=term-missing --cov-fail-under=70 -q
bash scripts/sdd-verify-spec.sh
bash scripts/ai-safety-gate.sh --verbose
bash scripts/conformance-check.sh
bash scripts/version-check.sh
```

All must exit 0. Existing 6 Gitflow workflows are untouched (no file
under `.github/workflows/{ci-core,develop-integration,feature-pr,hotfix,
release,ci-autofix}.yml` should appear in `git diff --stat` for this
branch). `git diff --stat` should show only: `core/protocols.py`
(additive), the new `workflow/` package, `.specify/`, `specs/001-.../`,
`scripts/sdd-verify-spec.sh`, `.github/workflows/sdd-gate.yml`,
`docs/SPECDRIVEN.md`, `CLAUDE.md` (additive §24), `pyproject.toml`
(one new dev dependency), and the corresponding `tests/` files.
