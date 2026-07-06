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
