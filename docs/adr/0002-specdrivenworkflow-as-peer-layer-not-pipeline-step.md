# ADR-0002: SpecDrivenWorkflow is a peer layer, not a respond() pipeline step

## Status

Accepted

## Context

GitHub Spec Kit's 11-phase SDD (Spec-Driven Development) methodology —
an 8-Article constitution, a gate catalog, and traceability-matrix
orphan detection — governs software-delivery *sequence and proof*: in
what order features get built, and what evidence proves each
requirement is met. This is a fundamentally different concern from
`OOAgent.respond()`'s job, which is answering one runtime query. The
naive integration would thread SDD-methodology checks into
`respond()`'s Template Method (CLAUDE.md §10) as new pipeline steps —
but `respond()`'s skeleton is explicitly frozen (CLAUDE.md §10: "No step
is skipped"), and SDD gates operate at a different cadence entirely
(once per delivery phase, not once per query).

## Decision

`IDeliveryWorkflow` is a fourth OOC (Object-Oriented Composition) layer,
orthogonal to `IDomainContext`, implemented once as `SpecDrivenWorkflow`
(`src/ooagent/workflow/spec_driven.py`). `core/agent.py`'s `respond()`
Template Method is untouched by this layer; `IDeliveryWorkflow` is a
peer object, never a pipeline step inside `respond()` (CLAUDE.md §24).
Gate *execution* is deliberately not `SpecDrivenWorkflow`'s own concern
— `.specify/gates/Makefile` is the DIP seam that binds gate names to
this repo's concrete tools (`mypy`, `ruff`, `pytest`, `pip-audit`,
`gitleaks`), enforced additively by `.github/workflows/sdd-gate.yml`
alongside the existing Gitflow CI workflows.

## Consequences

`respond()` remains a single, auditable Template Method with no
SDD-specific branching — the frozen §10 contract holds regardless of
whether `SpecDrivenWorkflow` is used at all. A project that doesn't want
SDD methodology simply never instantiates `SpecDrivenWorkflow`; there is
no conditional logic in `core/` to bypass. The trade-off is that
`IDeliveryWorkflow` and `IDomainContext` are two separate extension
points a contributor must learn are different (one governs delivery
process, one governs runtime domain knowledge) rather than a single
unified "workflow" concept — CLAUDE.md §24 exists specifically to make
that distinction explicit.
