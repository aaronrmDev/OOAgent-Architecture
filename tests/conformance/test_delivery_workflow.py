"""tests/conformance/test_delivery_workflow.py — IDeliveryWorkflow conformance (§17 CLAUDE.md)."""

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
