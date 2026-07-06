"""ooagent/workflow/gate_catalog.py — the 19-target gate contract (§5).

The DIP seam: this catalog declares gate NAMES and whether each is
required. Concrete execution commands live in .specify/gates/Makefile —
this module never shells out to run a tool.
"""

from __future__ import annotations

from ooagent.core.protocols import GateSpec

GATE_TARGETS: dict[str, GateSpec] = {
    "verify-spec": GateSpec(
        name="verify-spec",
        required=True,
        intent="SDD artifacts present + traceability resolved (§6)",
    ),
    "typecheck": GateSpec(
        name="typecheck",
        required=True,
        intent="static type verification",
    ),
    "lint": GateSpec(
        name="lint",
        required=True,
        intent="linter, zero warnings",
    ),
    "format-check": GateSpec(
        name="format-check",
        required=True,
        intent="formatter in check mode",
    ),
    "sast": GateSpec(
        name="sast",
        required=True,
        intent="static security analysis (OWASP ruleset)",
    ),
    "sca": GateSpec(
        name="sca",
        required=True,
        intent="dependency scan + SBOM emit (A03)",
    ),
    "secret-scan": GateSpec(
        name="secret-scan",
        required=True,
        intent="secret detection (A02)",
    ),
    "migrate": GateSpec(
        name="migrate",
        required=False,
        intent="apply schema migrations (if-db)",
    ),
    "test": GateSpec(
        name="test",
        required=True,
        intent="unit + integration + contract; emit coverage",
    ),
    "coverage-gate": GateSpec(
        name="coverage-gate",
        required=True,
        intent="fail below constitution threshold (ARTICLE VII)",
    ),
    "build": GateSpec(
        name="build",
        required=False,
        intent="build deployable/distributable (if-artifact)",
    ),
    "sign": GateSpec(
        name="sign",
        required=False,
        intent="sign artifact + provenance (A08, if-artifact)",
    ),
    "e2e": GateSpec(
        name="e2e",
        required=False,
        intent="end-to-end suite (if-ui)",
    ),
    "verify-signature": GateSpec(
        name="verify-signature",
        required=False,
        intent="verify signature before deploy (A08, if-deploy)",
    ),
    "deploy": GateSpec(
        name="deploy",
        required=False,
        intent="deploy gated on all-green (if-deploy)",
    ),
    "smoke": GateSpec(
        name="smoke",
        required=False,
        intent="post-deploy health (if-deploy)",
    ),
    "dast": GateSpec(
        name="dast",
        required=False,
        intent="dynamic security scan (if-deploy)",
    ),
    "alerting-probe": GateSpec(
        name="alerting-probe",
        required=False,
        intent="security logging/alerting reachable (A09, if-deploy)",
    ),
    "ledger": GateSpec(
        name="ledger",
        required=True,
        intent="append COBIT audit entry (ARTICLE III)",
    ),
}
