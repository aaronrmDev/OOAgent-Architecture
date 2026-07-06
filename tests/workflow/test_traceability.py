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
