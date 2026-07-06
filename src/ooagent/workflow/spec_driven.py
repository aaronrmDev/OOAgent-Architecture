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

    def verify_traceability(self, entries: tuple[TraceabilityEntry, ...]) -> tuple[GateResult, ...]:
        return _verify_traceability_entries(entries)
