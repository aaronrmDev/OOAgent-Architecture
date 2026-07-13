"""tests/workflow/test_traceability.py — §6 bidirectional traceability matrix validation."""

from __future__ import annotations

from pathlib import Path

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


def test_verify_traceability_passes_when_code_ref_and_ci_evidence_are_none() -> None:
    entry = TraceabilityEntry(
        req_id="REQ-6",
        ac_id="AC-6",
        task_id="TASK-6",
        test_id="tests/test_x.py::test_v",
        code_ref=None,
        ci_evidence=None,
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


def test_scan_spec_directory_resolves_a_fully_matched_req_ac_task_test(
    tmp_path: Path,
) -> None:
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
        "- [ ] **TASK-1** [P] Add the thing — file: `src/x.py` — "
        "implements REQ-1/AC-1\n"
        "  - **TEST-1**: `tests/test_x.py::test_thing_exists`\n",
        encoding="utf-8",
    )

    (entry,) = scan_spec_directory(spec_dir)
    assert entry.req_id == "REQ-1"
    assert entry.ac_id == "AC-1"
    assert entry.task_id == "TASK-1"
    assert entry.test_id == "tests/test_x.py::test_thing_exists"


def test_scan_spec_directory_flags_a_req_with_no_implementing_task_as_orphan(
    tmp_path: Path,
) -> None:
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


def test_scan_spec_directory_returns_empty_tuple_when_artifacts_missing(
    tmp_path: Path,
) -> None:
    from ooagent.workflow.traceability import scan_spec_directory

    empty_dir = tmp_path / "specs" / "000-empty"
    empty_dir.mkdir(parents=True)

    assert scan_spec_directory(empty_dir) == ()


def test_traceability_module_resolves_this_repos_own_spec_001() -> None:
    # The actual self-hosted proof, done through the Python module this time
    # instead of only scripts/sdd-verify-spec.sh (which duplicates this same
    # check in bash and is the thing CI currently runs).
    from ooagent.workflow.traceability import scan_specs_root, verify_traceability

    repo_root = Path(__file__).resolve().parents[2]
    entries = scan_specs_root(repo_root / "specs")

    assert len(entries) >= 6, (
        "expected at least 6 REQ/AC pairs from specs/001-spec-driven-workflow-layer"
    )

    results = verify_traceability(entries)
    failing = [r for r in results if not r.passed]
    assert failing == [], f"orphan traceability entries found: {failing}"
