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
