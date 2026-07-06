# 001 — Plan

## Stack (DIP injection point)

Python 3.11, `uv`, `mypy --strict`, `ruff`, `pytest` + `pytest-cov` — this
repo's existing stack (`docs/superpowers/specs/2026-07-04-python-port-design.md`).
Bash for `scripts/sdd-verify-spec.sh`. GNU Make for `.specify/gates/Makefile`.

## Architecture

`IDeliveryWorkflow` (ABC, `core/protocols.py`) is a peer layer to
`IDomainContext` — never invoked from `core/agent.py`'s `respond()`.
`SpecDrivenWorkflow` (`workflow/spec_driven.py`) is the sole
implementation, composed from `workflow/constitution.py` (Article data),
`workflow/gate_catalog.py` (GateSpec data), and `workflow/traceability.py`
(orphan-detection logic — a pure function, Information Expert on
traceability rules). Gate *execution* is explicitly out of this class's
responsibility (`binding = "gate-contract"`): `.specify/gates/Makefile`
is the DIP seam, per CLAUDE.md §3/§9 Adapter and Bridge pattern framing.

## Constitution Check

- ARTICLE I (Form): all new dataclasses are typed, frozen, no filler.
- ARTICLE II (Security): no new attack surface — no network calls, no
  secrets handled; existing AI Safety Gate/gitleaks/pip-audit scan the
  new files same as any other source file.
- ARTICLE III (Governance): `.specify/ledger/audit.log` gets its first
  real entries once `sdd-gate.yml` (Task 9) runs on a push.
- ARTICLE IV (Lifecycle): built on a feature branch via
  subagent-driven-development, merged to `develop` via the same Gitflow
  process as the Python port.
- ARTICLE V (Architecture): Information Expert (traceability module
  owns orphan rules), Pure Fabrication (`gate_catalog`/`constitution`
  have no real-world object counterpart, exist for cohesion), Adapter/
  Bridge (Makefile as DIP seam between gate names and concrete tools).
- ARTICLE VI (Testing): every task in `tasks.md` below pairs one
  implementation file with one test file, test written first.
- ARTICLE VII (Zero Defects): `coverage-gate` set to 70% (current
  measured baseline: 71%); this feature's own tests keep it at or above.
- ARTICLE VIII (Traceability): this very document is REQ-6's evidence.

## Gate Recipes Touched

`verify-spec` (new), `coverage-gate` (new), `ledger` (new), plus
`typecheck`/`lint`/`format-check`/`test` (already existed via
`ci-core.yml`, now also reachable through the Makefile for DIP-seam
parity — see `.github/workflows/sdd-gate.yml`).
