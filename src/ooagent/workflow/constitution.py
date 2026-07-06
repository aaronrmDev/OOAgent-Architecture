"""ooagent/workflow/constitution.py — the 8 Articles of the SDD constitution.

Human-readable projection: .specify/memory/constitution.md. Keep both in
sync — this module is the machine-readable source of truth.
"""

from __future__ import annotations

from ooagent.core.protocols import Article

ARTICLES: tuple[Article, ...] = (
    Article(
        numeral="I",
        title="Form",
        body=(
            "Artifact-first, typed, no filler, source-tagged. Every numeric "
            "claim carries a unit and a SourceTag (measured/assumed/cited/"
            "derived), per CLAUDE.md §15 Output Discipline."
        ),
        key="form",
    ),
    Article(
        numeral="II",
        title="Security",
        body=(
            "Secure-by-default; OWASP baseline enforced by the existing AI "
            "Safety Gate (13 guards), gitleaks secret scanning, and "
            "pip-audit dependency auditing. Gates block, they do not warn."
        ),
        key="security",
    ),
    Article(
        numeral="III",
        title="Governance",
        body=(
            "Client Accountable / engineer Responsible; every gate run is "
            "ledger-audited in .specify/ledger/audit.log."
        ),
        key="governance",
    ),
    Article(
        numeral="IV",
        title="Lifecycle",
        body=(
            "Gitflow (develop -> release/hotfix -> master) is the "
            "change-controlled lifecycle; every merge is a change record."
        ),
        key="lifecycle",
    ),
    Article(
        numeral="V",
        title="Architecture",
        body=(
            "SOLID/GRASP/GoF as codified in CLAUDE.md §§2-4; patterns "
            "reified as real objects, not comments. Default algorithmic "
            "complexity <= O(n); annotate deviations."
        ),
        key="architecture",
    ),
    Article(
        numeral="VI",
        title="Testing",
        body=(
            "TDD, non-negotiable: no implementation code before an "
            "approved failing test (Red), matching this repo's "
            "subagent-driven-development practice."
        ),
        key="testing",
    ),
    Article(
        numeral="VII",
        title="Zero Defects",
        body=(
            "Every requirement is testable; defect-escape-rate target is "
            "zero. Coverage floor enforced by the coverage-gate target and "
            "ratchets upward only, never down."
        ),
        key="zero-defects",
    ),
    Article(
        numeral="VIII",
        title="Traceability",
        body=(
            "spec -> task -> code -> test -> CI evidence, bidirectional, "
            "source-tagged. Orphans (code without a requirement, or a "
            "requirement without a test) are defects."
        ),
        key="traceability",
    ),
)
