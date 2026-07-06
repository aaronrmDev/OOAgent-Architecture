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
