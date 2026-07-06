# OOAgent — SDD Constitution

> Instantiated via `SpecDrivenWorkflow` (`src/ooagent/workflow/spec_driven.py`).
> Machine-readable source of truth: `src/ooagent/workflow/constitution.py`.
> This file is the human-readable projection; keep both in sync.

## ARTICLE I — Form

Artifact-first, typed, no filler, source-tagged. Every numeric claim
carries a unit and a SourceTag (measured/assumed/cited/derived), per
CLAUDE.md §15 Output Discipline.

## ARTICLE II — Security

Secure-by-default; OWASP baseline enforced by the existing AI Safety Gate
(13 guards), gitleaks secret scanning, and pip-audit dependency auditing.
Gates block, they do not warn.

## ARTICLE III — Governance

Client Accountable / engineer Responsible; every gate run is
ledger-audited in `.specify/ledger/audit.log`.

## ARTICLE IV — Lifecycle

Gitflow (`develop` -> `release`/`hotfix` -> `master`) is the
change-controlled lifecycle; every merge is a change record.

## ARTICLE V — Architecture

SOLID/GRASP/GoF as codified in CLAUDE.md §§2-4; patterns reified as real
objects, not comments. Default algorithmic complexity <= O(n); annotate
deviations.

## ARTICLE VI — Testing (NON-NEGOTIABLE)

TDD: no implementation code before an approved failing test (Red),
matching this repo's subagent-driven-development practice.

## ARTICLE VII — Zero Defects

Every requirement is testable; defect-escape-rate target is zero.
Coverage floor: **70%** (`pytest --cov-fail-under=70`), ratchets upward
only, never down.

## ARTICLE VIII — Traceability

spec -> task -> code -> test -> CI evidence, bidirectional, source-tagged.
Orphans (code without a requirement, or a requirement without a test) are
defects.
