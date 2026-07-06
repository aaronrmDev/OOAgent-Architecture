# SpecDrivenWorkflow / IDeliveryWorkflow — Design

## Purpose

Add the fourth OOC layer promised in the Python-port design
(`2026-07-04-python-port-design.md`): a pluggable, gate-enforced software
**delivery** process — orthogonal to `IDomainContext` (what OOAgent knows)
and any future persona layer (how OOAgent communicates).
`IDeliveryWorkflow` = in what order work happens, with what proof.

This is not a runtime query-answering concern. `OOAgent.respond()` (§10
CLAUDE.md) is untouched. `IDeliveryWorkflow` governs how *features get
built* — potentially features of OOAgent itself, or of any project that
forks this repo and wants the same discipline. The canonical methodology
is GitHub's Spec Kit SDD flow (`specify → clarify → plan → tasks → analyze →
implement → verify → handoff → support`), reified as real Python objects
plus a project-side gate contract (Makefile) plus CI enforcement — not
just documentation.

## Scope

**In scope:**

1. `IDeliveryWorkflow` ABC + supporting value objects in
   `core/protocols.py`, alongside the existing 11-interface catalog (§5
   CLAUDE.md).
2. Concrete `SpecDrivenWorkflow` implementation in a new
   `src/ooagent/workflow/` package — the 11-phase pipeline, the 8-Article
   constitution, the 19-target gate catalog, and traceability-matrix
   validation as real, testable logic.
3. `.specify/` scaffold at the repo root: `memory/constitution.md`,
   `templates/{spec,plan,tasks,checklist}.md`, `gates/Makefile` (recipes
   wired to this repo's **real** tools — `uv run mypy`, `ruff`,
   `pytest`, `pip-audit`, `gitleaks` — not blank stubs, since this repo
   is not greenfield), `ci/out/.gitkeep`, `ledger/audit.log` (seeded
   header line).
4. `scripts/sdd-verify-spec.sh` — traceability checker: every
   `specs/<NNN-slug>/` directory must have `spec.md`, `plan.md`,
   `tasks.md`, and every `REQ-*` in `spec.md` must resolve to at least one
   `TASK-*` and one `TEST-*` reference (grep-based, mirrors the existing
   `scripts/conformance-check.sh` style).
5. `.github/workflows/sdd-gate.yml` — new workflow, additive alongside
   the existing 6 Gitflow workflows (does not modify them). Runs
   `verify-spec`, `coverage-gate` (new — `pytest --cov-fail-under=70`,
   current baseline is 71%), and `ledger` via the Makefile DIP seam.
   Triggers on PRs to `develop` (mirrors `feature-pr.yml`'s trigger
   shape).
6. `specs/001-spec-driven-workflow-layer/{spec,plan,tasks}.md` — this
   feature, specified through its own process, so `verify-spec` has a
   real case on day one.
7. `docs/SPECDRIVEN.md` — this layer's CLAUDE.md-equivalent (the adapted
   template), plus a new §24 in `CLAUDE.md` referencing it (mirrors how
   §14 references `CONTEXT.md`).
8. Tests: `tests/conformance/test_delivery_workflow.py` (mirrors the
   existing `IAgent`/`IDomainContext`/`ITool`/`ILLMClient` conformance
   suites) + `tests/workflow/test_spec_driven_workflow.py` (unit tests
   for gate-chain ordering and traceability-matrix orphan detection).

**Out of scope** (conditional gates per the template's own design —
`if-artifact`/`if-deploy`, genuinely not applicable to a library with no
deployable service):

- `sign`, `e2e`, `verify-signature`, `deploy`, `smoke`, `dast`,
  `alerting-probe` — Makefile recipes exist (via the shared `_optional`
  helper, matching the pasted template exactly) and log a skip reason;
  no fake implementations.
- Rewriting `ci-core.yml`/`develop-integration.yml`/etc. to call through
  the Makefile. They already enforce equivalent gates directly and are
  confirmed green; converging them is a separate, later decision, not
  bundled with this feature.
- A real slash-command CLI (`/specify`, `/plan`, ...) wired into Claude
  Code or any other agent harness. This design ships the OOP layer, the
  scaffold, and the gate contract; command-surface integration is a
  future extension point (§9 of `docs/SPECDRIVEN.md`), consistent with
  CLAUDE.md §22's "Add a new domain context" extension protocol pattern.

## Package layout

```
src/ooagent/
  core/
    protocols.py          # + IDeliveryWorkflow, Phase, Article, GateSpec,
                           #   TraceabilityEntry, GateResult
  workflow/
    __init__.py            # barrel export
    spec_driven.py          # SpecDrivenWorkflow(IDeliveryWorkflow)
    constitution.py          # ARTICLES: tuple[Article, ...] — the 8 Articles
    gate_catalog.py         # GATE_TARGETS: dict[str, GateSpec] — the 19 targets
    traceability.py         # verify_traceability(entries) -> list[GateResult]

.specify/
  memory/constitution.md
  templates/{spec,plan,tasks,checklist}.md
  gates/Makefile
  ci/out/.gitkeep
  ledger/audit.log

specs/
  001-spec-driven-workflow-layer/
    spec.md  plan.md  tasks.md

scripts/
  sdd-verify-spec.sh

.github/workflows/
  sdd-gate.yml

docs/
  SPECDRIVEN.md

tests/
  conformance/test_delivery_workflow.py
  workflow/test_spec_driven_workflow.py
```

## Core contracts

`IDeliveryWorkflow` follows the same shape as `IDomainContext` — an
`abc.ABC`, no runtime dependencies beyond stdlib, consumed by nothing in
`core/agent.py` (it is a peer layer, not a pipeline step):

```python
class IDeliveryWorkflow(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    def phases(self) -> tuple[Phase, ...]: ...

    @abstractmethod
    def constitution(self) -> tuple[Article, ...]: ...

    @abstractmethod
    def gate_targets(self) -> dict[str, GateSpec]: ...

    @abstractmethod
    def gate_chain(self, phase_name: str) -> tuple[str, ...]: ...

    @abstractmethod
    def verify_traceability(
        self, entries: tuple[TraceabilityEntry, ...]
    ) -> tuple[GateResult, ...]: ...
```

Value objects (frozen `@dataclass`, matching the existing catalog's
convention):

- `Phase(name, artifact, itil_stage, cobit_domain, owasp_gate, oop_pattern)`
  — one row per §2 pipeline stage (11 phases, `/constitution` through
  `/support`).
- `Article(numeral, title, body, key)` — one per constitution Article
  (I–VIII).
- `GateSpec(name, required, intent)` — one per §5 gate target (19 total).
- `TraceabilityEntry(req_id, ac_id, task_id, test_id, code_ref, ci_evidence)`
  — one row of the §6 bidirectional matrix; `code_ref`/`ci_evidence` are
  `str | None` (not yet resolved is a valid, checkable state).
- `GateResult(gate_name, passed, message)` — returned by
  `verify_traceability()`; orphan detection (a `TraceabilityEntry` missing
  `task_id` or `test_id`) produces a failing `GateResult`, matching §6's
  "Orphans ... are defects."

`SpecDrivenWorkflow` is the concrete implementation: `name="spec-driven"`,
`version="2026.07.001"` (CalVer `YYYY.MM.NNN` — the pasted template's own
scheme; this is the class's *own* independent version property, distinct
from `pyproject.toml`'s package version, exactly as CLAUDE.md §18 already
requires for `IDomainContext` implementations: "impls version
independently ... declare their own semver in `context.version`"), the
11 `Phase` rows from §2, the 8 `Article` rows from §1 (text
adapted below), the 19 `GateSpec` rows from §5, and
`verify_traceability()` implementing the orphan-detection rule from §6.
Gate *execution* (actually running `mypy`, `pytest`, etc.) is explicitly
**not** this class's job — `binding = "gate-contract"` means the Makefile
is the DIP seam (Information Expert: the Makefile is the expert on how to
run a tool; `SpecDrivenWorkflow` is the expert on structure and
traceability).

## The 8 Articles, adapted to this repo

The pasted template's Articles map onto CLAUDE.md's existing principles
almost verbatim — this repo already practices most of them; the
constitution makes the practice explicit and auditable:

```
I    Form            — CLAUDE.md §15 Output Discipline: source-tagged
                        numeric claims, typed code, no filler.
II   Security         — the existing AI Safety Gate (13 guards) +
                        gitleaks + pip-audit ARE the ASVS baseline;
                        this Article makes them constitution-level.
III  Governance       — CONTRIBUTORS.md's review process; ledger.md is
                        the new audit trail this feature adds.
IV   Lifecycle        — Gitflow (develop/master/release/hotfix) IS the
                        ITIL-flavored lifecycle already in place.
V    Architecture     — CLAUDE.md §2/§3/§4 (SOLID/GRASP/GoF) verbatim.
VI   Testing          — TDD, non-negotiable: matches this repo's
                        existing subagent-driven-development practice
                        (test written and failing before implementation).
VII  Zero Defects     — coverage-gate (70% floor, ratchets up only) +
                        defect-escape-rate tracked via ledger entries.
VIII Traceability     — the new specs/<NNN>/{spec,plan,tasks}.md +
                        verify-spec gate.
```

## Gate contract mapping (§5 of the pasted template)

| gate target | required? | this repo's concrete binding |
|---|---|---|
| verify-spec | yes | **new** — `scripts/sdd-verify-spec.sh` |
| typecheck | yes | `uv run mypy --strict` (already in `ci-core.yml`) |
| lint | yes | `uv run ruff check` (already in `ci-core.yml`) |
| format-check | yes | `uv run ruff format --check` (already in `ci-core.yml`) |
| sast | yes | `scripts/ai-safety-gate.sh` (already in `ci-core.yml`) |
| sca | yes | `pip-audit` (already in `ci-core.yml`) |
| secret-scan | yes | `gitleaks` (already in `ci-core.yml`) |
| migrate | if-db | `_optional` skip — no DB in this project |
| test | yes | `PYTHONPATH=src uv run pytest tests/` |
| coverage-gate | yes | **new** — `pytest --cov=ooagent --cov-fail-under=70` |
| build | if-artifact | `uv build` (already in `ci-core.yml`) |
| sign | if-artifact | `_optional` skip — no signed artifact today |
| e2e | if-ui | `_optional` skip — no UI |
| verify-signature | if-deploy | `_optional` skip — no deploy pipeline |
| deploy | if-deploy | `_optional` skip |
| smoke | if-deploy | `_optional` skip |
| dast | if-deploy | `_optional` skip |
| alerting-probe | if-deploy | `_optional` skip |
| ledger | yes | **new** — append line to `.specify/ledger/audit.log` |

The Makefile is the literal artifact from §5 of the pasted template,
values filled in per this table. `sdd-gate.yml` calls only the **new**
three targets (`verify-spec`, `coverage-gate`, `ledger`) plus re-runs
`typecheck`/`lint`/`test` through the Makefile as a proof that the DIP
seam actually works end-to-end (both the Makefile path and `ci-core.yml`
must agree — if they diverge, that is itself a defect the constitution's
Article VII was written to catch).

## Testing

- `tests/conformance/test_delivery_workflow.py` — same shape as the
  existing 4 conformance suites: `phases()` non-empty,
  `constitution()` returns exactly 8 `Article` entries,
  `gate_targets()` returns exactly 19 `GateSpec` entries,
  `verify_traceability(())` (empty tuple) returns `()` without raising.
- `tests/workflow/test_spec_driven_workflow.py` — unit tests:
  `gate_chain()` ordering is deterministic and matches §3's documented
  order (`g_form → g_security → g_governance → g_lifecycle →
  g_traceability → g_correctness`); `verify_traceability()` flags an
  entry missing `task_id` or `test_id` as a failing `GateResult` and
  passes a fully-resolved entry.

## Docs

- `docs/SPECDRIVEN.md` — the adapted template in full (identity block,
  bootstrap, constitution text, phase pipeline, gate chain, zero-defects
  contract, gate-contract table, traceability matrix, command
  integration, composition-with-OOAgent section, anti-patterns).
- `CLAUDE.md` new §24 "IDeliveryWorkflow — SpecDrivenWorkflow Layer":
  2–3 paragraphs summarizing the layer and pointing to
  `docs/SPECDRIVEN.md`, mirroring §14's `CONTEXT.md` cross-reference
  pattern. No changes to any existing CLAUDE.md section.

## Rollout

Single coherent feature branch (per this repo's established worktree +
subagent-driven-development pattern), sequenced as:

1. `core/protocols.py` additions (value objects + `IDeliveryWorkflow` ABC).
2. `src/ooagent/workflow/` package (constitution, gate catalog,
   traceability, `SpecDrivenWorkflow`).
3. Conformance + unit tests for the above.
4. `.specify/` scaffold + `scripts/sdd-verify-spec.sh`.
5. `specs/001-spec-driven-workflow-layer/{spec,plan,tasks}.md`
   (self-hosting proof — written to describe *this exact feature*,
   satisfying its own `verify-spec` gate).
6. `.github/workflows/sdd-gate.yml`.
7. `docs/SPECDRIVEN.md` + `CLAUDE.md` §24.
8. Verify: `mypy --strict`, `ruff check`, `pytest` (full suite,
   `--cov-fail-under=70`), `bash scripts/sdd-verify-spec.sh` all green
   locally before merge; existing 6 Gitflow workflows untouched and
   still green (no regression risk — this is purely additive).

## Out-of-scope confirmation

No existing file's *behavior* changes. `ci-core.yml`,
`develop-integration.yml`, `feature-pr.yml`, `hotfix.yml`, `release.yml`,
`ci-autofix.yml` are read but not modified. `core/agent.py`'s `respond()`
Template Method is read but not modified — `IDeliveryWorkflow` is a peer
layer, never invoked from the request-handling path.
