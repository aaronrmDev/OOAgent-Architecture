# Traceability Module Self-Hosted Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/ooagent/workflow/traceability.py`'s `verify_traceability` is currently only ever called with hand-built `TraceabilityEntry` literals in tests — nothing in the codebase parses `specs/<slug>/{spec.md,tasks.md}` into real entries. The actual self-hosted proof against this repo's own `specs/001-spec-driven-workflow-layer/` runs entirely through a separate, parallel bash implementation (`scripts/sdd-verify-spec.sh`) that never calls into the Python module. This plan adds a real parser that turns `spec.md` + `tasks.md` into `TraceabilityEntry` tuples, and a test that runs it against this repo's actual `specs/` directory — making `traceability.py` the thing that's genuinely proven, not just documented as such.

**Architecture:** Two pure functions in `workflow/traceability.py`: `scan_spec_directory(spec_dir: Path) -> tuple[TraceabilityEntry, ...]` (parses one `specs/<slug>/` directory) and `scan_specs_root(specs_root: Path) -> tuple[TraceabilityEntry, ...]` (scans every subdirectory and concatenates). Both are pure — no side effects beyond file reads, matching `verify_traceability`'s existing pure-function style (the module's docstring already calls it "Information Expert on traceability rules" — this plan makes that expertise actually reach real files). A convenience method on `SpecDrivenWorkflow` composes scan + verify for callers that want "traceability-check this specs root" in one call. This plan does **not** touch `scripts/sdd-verify-spec.sh` or `.specify/gates/Makefile` — the bash script remains the CI-enforced gate (rewriting a CI-critical path is out of scope here); this plan makes the Python module's own claim to "reify" traceability checking actually true, additively.

**Tech Stack:** Python 3.11 stdlib (`re`, `pathlib.Path`), pytest, mypy --strict, ruff.

## Global Constraints

- `mypy --strict` and `ruff` (`select = ["E", "F", "I", "UP", "B"]`, line-length 100) must pass on every touched file.
- No new runtime dependencies.
- `workflow/` depends only on `core/protocols.py` per CLAUDE.md §7 package rules — do not import from `core/agent.py` or any other `core/` module, and do not import `subprocess`/shell out to the bash script.
- Existing tests in `tests/workflow/test_traceability.py` and `tests/workflow/test_spec_driven_workflow.py` must continue to pass unmodified.

---

### Task 1: Add `scan_spec_directory` — parse one `specs/<slug>/` directory into `TraceabilityEntry` tuples

**Files:**
- Modify: `src/ooagent/workflow/traceability.py` (add parsing functions, after the existing `verify_traceability`)
- Test: `tests/workflow/test_traceability.py`

**Interfaces:**
- Consumes: `TraceabilityEntry` (existing, `core/protocols.py:617-624`).
- Produces: `scan_spec_directory(spec_dir: Path) -> tuple[TraceabilityEntry, ...]` — parses `spec_dir/spec.md` for `**REQ-N**`/`**AC-M**` pairs and `spec_dir/tasks.md` for `**TASK-K**` entries carrying an `implements REQ-N/AC-M` reference and a paired `**TEST-K**: \`ref\`` line; returns `()` if either file is missing (artifact-presence checking stays `scripts/sdd-verify-spec.sh`'s job, not this function's).

- [ ] **Step 1: Write the failing test**

Add to `tests/workflow/test_traceability.py`:

```python
def test_scan_spec_directory_resolves_a_fully_matched_req_ac_task_test(tmp_path) -> None:
    from pathlib import Path

    from ooagent.workflow.traceability import scan_spec_directory

    spec_dir = tmp_path / "specs" / "001-example"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text(
        "## Requirements\n\n"
        "- **REQ-1**: something must exist.\n"
        "  - **AC-1**: something is verifiably true.\n",
        encoding="utf-8",
    )
    (spec_dir / "tasks.md").write_text(
        "- [ ] **TASK-1** [P] Add the thing — file: `src/x.py` — implements REQ-1/AC-1\n"
        "  - **TEST-1**: `tests/test_x.py::test_thing_exists`\n",
        encoding="utf-8",
    )

    (entry,) = scan_spec_directory(spec_dir)
    assert entry.req_id == "REQ-1"
    assert entry.ac_id == "AC-1"
    assert entry.task_id == "TASK-1"
    assert entry.test_id == "tests/test_x.py::test_thing_exists"


def test_scan_spec_directory_flags_a_req_with_no_implementing_task_as_orphan(tmp_path) -> None:
    from ooagent.workflow.traceability import scan_spec_directory

    spec_dir = tmp_path / "specs" / "999-orphan"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text(
        "- **REQ-1**: something must exist.\n  - **AC-1**: something is true.\n",
        encoding="utf-8",
    )
    (spec_dir / "tasks.md").write_text(
        "- [ ] **TASK-1** does unrelated work\n  - **TEST-1**: `tests/test_y.py::test_y`\n",
        encoding="utf-8",
    )

    (entry,) = scan_spec_directory(spec_dir)
    assert entry.task_id is None
    assert entry.test_id is None


def test_scan_spec_directory_returns_empty_tuple_when_artifacts_missing(tmp_path) -> None:
    from ooagent.workflow.traceability import scan_spec_directory

    empty_dir = tmp_path / "specs" / "000-empty"
    empty_dir.mkdir(parents=True)

    assert scan_spec_directory(empty_dir) == ()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/workflow/test_traceability.py -v -k scan_spec_directory`
Expected: FAIL with `ImportError: cannot import name 'scan_spec_directory'`

- [ ] **Step 3: Implement**

In `src/ooagent/workflow/traceability.py`, replace the full file contents with:

```python
"""ooagent/workflow/traceability.py — §6 bidirectional traceability matrix validation.

An entry is an orphan (§6 CLAUDE.md-equivalent, docs/SPECDRIVEN.md §6) when
it lacks a task_id or a test_id — code without a requirement, or a
requirement without a test, is a defect.
"""

from __future__ import annotations

import re
from pathlib import Path

from ooagent.core.protocols import GateResult, TraceabilityEntry

_REQ_LINE = re.compile(r"-\s+\*\*(?P<req_id>REQ-\d+)\*\*")
_AC_LINE = re.compile(r"-\s+\*\*(?P<ac_id>AC-\d+)\*\*")
_TASK_LINE = re.compile(r"\*\*(?P<task_id>TASK-\d+)\*\*")
_IMPLEMENTS = re.compile(r"implements\s+(?P<req_id>REQ-\d+)/(?P<ac_id>AC-\d+)")
_TEST_LINE = re.compile(r"\*\*TEST-\d+\*\*:\s*`(?P<test_ref>[^`]+)`")


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
                        f"{entry.req_id}/{entry.ac_id} is an orphan: missing {', '.join(missing)}"
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


def _parse_spec_requirements(spec_md: str) -> list[tuple[str, str]]:
    """Returns [(req_id, ac_id), ...] in file order. A REQ line establishes
    the "current" requirement; every AC line until the next REQ line pairs
    with it — supports one or more AC entries per REQ."""
    pairs: list[tuple[str, str]] = []
    current_req: str | None = None
    for line in spec_md.splitlines():
        ac_match = _AC_LINE.search(line)
        if ac_match and current_req is not None:
            pairs.append((current_req, ac_match.group("ac_id")))
            continue
        req_match = _REQ_LINE.search(line)
        if req_match:
            current_req = req_match.group("req_id")
    return pairs


def _parse_tasks(tasks_md: str) -> dict[tuple[str, str], tuple[str, str | None]]:
    """Returns {(req_id, ac_id): (task_id, test_id)}. A task block is the
    "- [ ] **TASK-N** ... implements REQ-x/AC-y" line plus the nearest
    following "**TEST-M**: `ref`" line (searched within the next 3 lines,
    matching this repo's tasks.md convention of one indented TEST line
    immediately under its TASK line)."""
    resolved: dict[tuple[str, str], tuple[str, str | None]] = {}
    lines = tasks_md.splitlines()
    for i, line in enumerate(lines):
        task_match = _TASK_LINE.search(line)
        implements_match = _IMPLEMENTS.search(line)
        if not (task_match and implements_match):
            continue
        task_id = task_match.group("task_id")
        req_id = implements_match.group("req_id")
        ac_id = implements_match.group("ac_id")
        test_id: str | None = None
        for follow in lines[i + 1 : i + 4]:
            test_match = _TEST_LINE.search(follow)
            if test_match:
                test_id = test_match.group("test_ref")
                break
        resolved[(req_id, ac_id)] = (task_id, test_id)
    return resolved


def scan_spec_directory(spec_dir: Path) -> tuple[TraceabilityEntry, ...]:
    """Builds TraceabilityEntry tuples from a single specs/<slug>/
    directory's spec.md + tasks.md — the Information Expert on turning SDD
    markdown artifacts into structured traceability data. A REQ/AC pair with
    no matching "implements REQ-x/AC-y" task is an orphan (task_id/test_id
    both None), mirroring scripts/sdd-verify-spec.sh's orphan rule. Returns
    an empty tuple if either artifact is missing — artifact-presence
    checking is scripts/sdd-verify-spec.sh's responsibility, not this
    function's."""
    spec_path = spec_dir / "spec.md"
    tasks_path = spec_dir / "tasks.md"
    if not spec_path.is_file() or not tasks_path.is_file():
        return ()

    requirements = _parse_spec_requirements(spec_path.read_text(encoding="utf-8"))
    resolved = _parse_tasks(tasks_path.read_text(encoding="utf-8"))

    entries: list[TraceabilityEntry] = []
    for req_id, ac_id in requirements:
        match = resolved.get((req_id, ac_id))
        task_id: str | None = match[0] if match else None
        test_id: str | None = match[1] if match else None
        entries.append(
            TraceabilityEntry(
                req_id=req_id,
                ac_id=ac_id,
                task_id=task_id,
                test_id=test_id,
                code_ref=None,
                ci_evidence=None,
            )
        )
    return tuple(entries)


def scan_specs_root(specs_root: Path) -> tuple[TraceabilityEntry, ...]:
    """Scans every specs/<slug>/ directory under `specs_root` (sorted by
    name for deterministic ordering) and concatenates their
    TraceabilityEntry tuples."""
    if not specs_root.is_dir():
        return ()
    entries: list[TraceabilityEntry] = []
    for child in sorted(specs_root.iterdir()):
        if child.is_dir():
            entries.extend(scan_spec_directory(child))
    return tuple(entries)
```

- [ ] **Step 4: Run tests to verify they pass, and confirm no regressions**

Run: `pytest tests/workflow/test_traceability.py -v`
Expected: all PASS, including the 6 pre-existing synthetic-fixture tests (unmodified, still importing `verify_traceability` which is unchanged) and the 3 new `scan_spec_directory` tests.

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/workflow/traceability.py tests/workflow/test_traceability.py
git commit -m "feat(workflow): parse specs/<slug>/ spec.md+tasks.md into TraceabilityEntry tuples"
```

---

### Task 2: Prove it against this repo's own `specs/001-spec-driven-workflow-layer/` — the actual self-hosted check

**Files:**
- Test: `tests/workflow/test_traceability.py`

**Interfaces:**
- Consumes: `scan_specs_root`, `verify_traceability` from Task 1.

- [ ] **Step 1: Write the test**

Add to `tests/workflow/test_traceability.py`:

```python
def test_traceability_module_resolves_this_repos_own_spec_001() -> None:
    # The actual self-hosted proof, done through the Python module this time
    # instead of only scripts/sdd-verify-spec.sh (which duplicates this same
    # check in bash and is the thing CI currently runs).
    from pathlib import Path

    from ooagent.workflow.traceability import scan_specs_root, verify_traceability

    repo_root = Path(__file__).resolve().parents[2]
    entries = scan_specs_root(repo_root / "specs")

    assert len(entries) >= 6, "expected at least the 6 REQ/AC pairs from specs/001-spec-driven-workflow-layer"

    results = verify_traceability(entries)
    failing = [r for r in results if not r.passed]
    assert failing == [], f"orphan traceability entries found: {failing}"
```

- [ ] **Step 2: Run test to verify it currently fails or passes for the right reason**

Run: `pytest tests/workflow/test_traceability.py::test_traceability_module_resolves_this_repos_own_spec_001 -v`

Expected: this should PASS immediately given Task 1's implementation and the real, already-correct content of `specs/001-spec-driven-workflow-layer/spec.md` and `tasks.md` (verified during planning: 6 REQ/AC pairs, each with a matching `implements REQ-N/AC-N` task and paired TEST line). If it fails, read the assertion failure carefully — it means either the parser has a bug (re-check `_parse_spec_requirements`/`_parse_tasks` against the exact real file content) or `specs/001-spec-driven-workflow-layer/` has actually drifted from what this plan assumed; in the latter case, do not weaken the test — investigate the real spec files.

- [ ] **Step 3: N/A — no implementation step; this task's value is the test itself proving Task 1's parser against real data**

- [ ] **Step 4: Re-run to confirm stability**

Run: `pytest tests/workflow/test_traceability.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/workflow/test_traceability.py
git commit -m "test(workflow): prove traceability.py resolves this repo's own specs/001 self-hosted"
```

---

### Task 3: Add a `SpecDrivenWorkflow` convenience method composing scan + verify

**Files:**
- Modify: `src/ooagent/workflow/spec_driven.py`
- Test: `tests/workflow/test_spec_driven_workflow.py`

**Interfaces:**
- Consumes: `scan_specs_root` (Task 1), `verify_traceability` (existing, already imported in `spec_driven.py` as `_verify_traceability_entries`).
- Produces: `SpecDrivenWorkflow.verify_traceability_for_specs_root(self, specs_root: Path) -> tuple[GateResult, ...]` — a new method, additive to the concrete class (not the `IDeliveryWorkflow` ABC — CLAUDE.md §24's extension protocol says a second implementation requires "no edits to `core/protocols.py`"; this stays consistent by keeping the composition convenience on the concrete class only).

- [ ] **Step 1: Write the failing test**

Add to `tests/workflow/test_spec_driven_workflow.py`:

```python
def test_verify_traceability_for_specs_root_resolves_this_repos_spec_001() -> None:
    from pathlib import Path

    from ooagent.workflow.spec_driven import SpecDrivenWorkflow

    repo_root = Path(__file__).resolve().parents[2]
    workflow = SpecDrivenWorkflow()

    results = workflow.verify_traceability_for_specs_root(repo_root / "specs")

    assert len(results) >= 6
    assert all(r.passed for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/workflow/test_spec_driven_workflow.py::test_verify_traceability_for_specs_root_resolves_this_repos_spec_001 -v`
Expected: FAIL with `AttributeError: 'SpecDrivenWorkflow' object has no attribute 'verify_traceability_for_specs_root'`

- [ ] **Step 3: Implement**

In `src/ooagent/workflow/spec_driven.py`, update the import at line 20:

```python
from ooagent.workflow.traceability import verify_traceability as _verify_traceability_entries
```

to:

```python
from ooagent.workflow.traceability import scan_specs_root as _scan_specs_root
from ooagent.workflow.traceability import verify_traceability as _verify_traceability_entries
```

Add `Path` to the imports at the top of the file (`from pathlib import Path`, placed with the other stdlib imports — currently the file has no stdlib imports beyond the `from __future__ import annotations` at line 8, so add `from pathlib import Path` as a new import block after it).

Add the new method to `SpecDrivenWorkflow`, directly after `verify_traceability` (line 148-149):

```python
    def verify_traceability(self, entries: tuple[TraceabilityEntry, ...]) -> tuple[GateResult, ...]:
        return _verify_traceability_entries(entries)

    def verify_traceability_for_specs_root(self, specs_root: Path) -> tuple[GateResult, ...]:
        """Composes scan_specs_root + verify_traceability — the one-call path
        for "traceability-check every specs/<slug>/ under this root"."""
        return self.verify_traceability(_scan_specs_root(specs_root))
```

- [ ] **Step 4: Run test to verify it passes, and confirm no regressions**

Run: `pytest tests/workflow/test_spec_driven_workflow.py -v`
Expected: all PASS, including the pre-existing `test_verify_traceability_delegates_to_traceability_module`.

Run: `pytest tests/workflow/ tests/conformance/test_delivery_workflow.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ooagent/workflow/spec_driven.py tests/workflow/test_spec_driven_workflow.py
git commit -m "feat(workflow): SpecDrivenWorkflow.verify_traceability_for_specs_root composes scan+verify"
```

---

### Task 4: Full-suite regression check and static analysis

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all PASS.

- [ ] **Step 2: Run mypy --strict**

Run: `mypy --strict src/ooagent`
Expected: no errors — pay attention to the `dict[tuple[str, str], tuple[str, str | None]]` typing in `_parse_tasks` and the `Path` return types throughout `traceability.py`.

- [ ] **Step 3: Run ruff**

Run: `ruff check src/ooagent tests`
Expected: no errors.

- [ ] **Step 4: Commit if any lint-only fixups were needed**

```bash
git add -A
git commit -m "chore: lint/type fixups for traceability wiring work"
```

(Skip this commit entirely if steps 1-3 were already clean.)
