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
