# 001 — SpecDrivenWorkflow / IDeliveryWorkflow Layer

## Requirements

- **REQ-1**: `IDeliveryWorkflow` and its value objects exist in `core/protocols.py`.
  - **AC-1**: `IDeliveryWorkflow` cannot be instantiated directly (raises `TypeError`); `Phase`/`Article`/`GateSpec`/`TraceabilityEntry`/`GateResult` are frozen dataclasses.
- **REQ-2**: `SpecDrivenWorkflow` provides exactly 8 constitution Articles.
  - **AC-2**: `constitution()` returns exactly 8 `Article` entries, numerals `I` through `VIII` in order.
- **REQ-3**: `SpecDrivenWorkflow` provides exactly 19 gate targets matching §5 of the design.
  - **AC-3**: `gate_targets()` returns exactly 19 `GateSpec` entries; the 9 conditional gates are not required.
- **REQ-4**: Traceability verification flags orphan entries as failing.
  - **AC-4**: `verify_traceability()` returns a failing `GateResult` for an entry missing `task_id` or `test_id`, and a passing `GateResult` for a fully-resolved entry.
- **REQ-5**: The `.specify/` scaffold provides a runnable, project-bound gate contract instead of blank stubs.
  - **AC-5**: `.specify/gates/Makefile` defines a recipe for every gate in the catalog; every *required* gate's recipe is a real command, not the `_optional` skip helper.
- **REQ-6**: The `verify-spec` gate blocks on missing or orphaned SDD artifacts.
  - **AC-6**: `scripts/sdd-verify-spec.sh` exits non-zero when a `specs/<slug>/` directory is missing an artifact or has an orphan `REQ`/`TASK`/`TEST`, and exits 0 when this very feature's `specs/001-spec-driven-workflow-layer/` is fully resolved.

## User Stories

As a maintainer of OOAgent (or a fork of it), I want a gate-enforced,
traceable delivery process for new features, so that every requirement
ships with proof (a test, a code reference, CI evidence) rather than
relying on review discipline alone.

## Success Criteria

All of REQ-1 through REQ-6 hold, verified by their paired tests (see
`tasks.md`), and `bash scripts/sdd-verify-spec.sh` exits 0 against this
very `specs/001-spec-driven-workflow-layer/` directory.

## Edge Cases & Abuse Cases

- A future spec directory ships `spec.md`/`plan.md` but forgets
  `tasks.md` — `verify-spec` must fail closed (missing-artifact check).
- A future spec references a `REQ-id` with no implementing task —
  `verify-spec` must flag it as an orphan requirement.
- A future `tasks.md` has more `TASK-*` entries than `TEST-*` entries
  (a task with no paired test) — `verify-spec` must fail on the count
  mismatch (ARTICLE VI).

## Out of Scope

A real slash-command CLI (`/specify`, `/plan`, ...) wired into an agent
harness; rewriting the existing 6 Gitflow workflows to call through the
Makefile; `sign`/`e2e`/`deploy`/`smoke`/`dast`/`verify-signature`/
`alerting-probe` gates (no deployable service exists for this library).
