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
