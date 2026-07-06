# SpecDrivenWorkflow — IDeliveryWorkflow implementation

> Fourth OOC layer. Plugs into `OOAgent` (`CLAUDE.md`) orthogonally to
> `IDomainContext`. `IDomainContext` = what · `IDeliveryWorkflow` = in
> what order, with what proof. Project-agnostic: knows gate **names and
> order**, never a stack. Concretes are DIP-injected per project via
> `.specify/gates/Makefile`. Canonical methodology: GitHub Spec Kit SDD
> flow.

---

## 0. Identity

```python
class SpecDrivenWorkflow(IDeliveryWorkflow):
    name    = "spec-driven"
    version = "2026.07.001"    # CalVer YYYY.MM.NNN — independent of
                                # pyproject.toml's package version
                                # (CLAUDE.md §18 — impls version
                                # independently)
```

Implementation: `src/ooagent/workflow/spec_driven.py`.

---

## 0.1 Bootstrap status (this repo)

This repo is not greenfield — the scaffold below already exists,
instantiated for this exact codebase:

```
.specify/
  memory/constitution.md            # the 8 Articles, this repo's bindings
  templates/{spec,plan,tasks,checklist}.md
  gates/Makefile                    # filled — uv/mypy/ruff/pytest/pip-audit/gitleaks
  ci/out/                           # gate evidence (coverage.xml) by convention
  ledger/audit.log                  # COBIT audit trail (ARTICLE III)
specs/                              # per-feature: <NNN-slug>/{spec,plan,tasks}.md
.github/workflows/sdd-gate.yml      # additive CI orchestrator
```

A downstream fork starting from scratch instead blanks
`constitution.md`'s bindings and `gates/Makefile`'s recipes until its own
`/plan`-equivalent phase fills them in — the structure and gate *names*
are what transfer verbatim; the concrete commands are per-project.

---

## 1. The Constitution

`.specify/memory/constitution.md` (human-readable) and
`src/ooagent/workflow/constitution.py` (`ARTICLES`, machine-readable) are
kept in sync. Every downstream phase validates against it:

```
ARTICLE I    — Form            : artifact-first, typed, no filler, source-tagged.
ARTICLE II   — Security        : OWASP baseline; AI Safety Gate + gitleaks + pip-audit block, not warn.
ARTICLE III  — Governance      : client Accountable / engineer Responsible; ledger-audited.
ARTICLE IV   — Lifecycle       : Gitflow is the change-controlled lifecycle.
ARTICLE V    — Architecture    : SOLID/GRASP/GoF (CLAUDE.md §§2-4); patterns reified.
ARTICLE VI   — Testing         : TDD, NON-NEGOTIABLE.
ARTICLE VII  — Zero Defects    : coverage floor 70%, ratchets up only.
ARTICLE VIII — Traceability    : spec → task → code → test → CI evidence, bidirectional.
```

Amending the constitution is a logged decision — edit both
`constitution.md` and `constitution.py` together, in the same commit.

---

## 2. Phase Pipeline (11 phases; Template Method skeleton)

```
# phase          artifact               ITIL                COBIT  OWASP gate            OOP
/constitution     constitution.md        (baseline)          EDM    A06 threat baseline   invariants
/specify          spec.md                Engage              APO    abuse-cases noted     —
/clarify          spec.md (revised)      Engage              APO    ambiguity = risk      Protected Variations
/plan             plan.md                Design&Transition   BAI    /threat-model, ASVS   DIP stack + gate inject
/checklist        checklist.md           Design&Transition   MEA    security checklist    self-check
/tasks            tasks.md               Build (prep)        BAI    security task/story   Command (reified [P])
/analyze          analysis (read-only)   (gate)              MEA    sec-req coverage      Chain of Responsibility
/implement        code + tests           Build               BAI    A01–A10 by default    all
/verify (CI/CD)   ci evidence            Design→Deliver      MEA    gate-contract run     —
/handoff          handoff pack           Transition(release) EDM    logging/alerting xfer —
/support          change records         Deliver&Support     DSS    incident→problem      —
```

Source: `PHASES` in `src/ooagent/workflow/spec_driven.py`.

---

## 3. Gate Chain (per phase, exit gates only — entry is "predecessor exists")

```
g_form          ARTICLE I satisfied?             → strip/rewrite
g_security      ARTICLE II OWASP baseline met?    → harden, re-enter
g_governance    ARTICLE III RACI + source-tags?   → annotate + ledger
g_lifecycle     ARTICLE IV stage declared?        → declare
g_traceability  ARTICLE VIII links resolved?      → backfill matrix
g_correctness   requirement/AC actually met?      → correct (final authority)
```

Precedence: **correctness ⊐ security ⊐ governance ⊐ lifecycle ⊐ form**.
Same chain for every phase — `SpecDrivenWorkflow.gate_chain(phase_name)`
returns this tuple regardless of which valid phase name is passed.

---

## 4. Zero Defects contract

```
defect class      owning prevention gate
  spec defect       → /clarify + /analyze
  design defect     → /plan
  contract defect   → /checklist
  code defect       → TDD Red→Green + typecheck + lint (ARTICLE VI)
  security defect   → sast/sca/secret-scan (ARTICLE II)
  regression        → full suite per change (ARTICLE VIII)

invariants:
  - Every spec requirement carries >=1 testable acceptance criterion.
  - No implementation precedes its failing test.
  - Requirement→test coverage = 100%; line coverage >= 70% (ratchets up).
  - All CI gates BLOCKING. No skip/continue-on-error on required gates.
  - Definition of Done = all exit gates green + CI green + ledger entry.
```

---

## 5. Gate Contract — concrete bindings for this repo

| gate target | required? | this repo's binding |
|---|---|---|
| verify-spec | yes | `scripts/sdd-verify-spec.sh` |
| typecheck | yes | `uv run mypy --strict` |
| lint | yes | `uv run ruff check` |
| format-check | yes | `uv run ruff format --check` |
| sast | yes | `scripts/ai-safety-gate.sh` |
| sca | yes | `pip-audit` |
| secret-scan | yes | `gitleaks` |
| migrate | no | N/A — no DB |
| test | yes | `pytest tests/` |
| coverage-gate | yes | `pytest --cov-fail-under=70` |
| build | no | `uv build` (enabled — real recipe) |
| sign | no | N/A — no signed artifact |
| e2e | no | N/A — no UI |
| verify-signature | no | N/A — no deploy pipeline |
| deploy | no | N/A |
| smoke | no | N/A |
| dast | no | N/A |
| alerting-probe | no | N/A |
| ledger | yes | append to `.specify/ledger/audit.log` |

Source: `GATE_TARGETS` in `src/ooagent/workflow/gate_catalog.py`;
recipes in `.specify/gates/Makefile`.

---

## 6. Traceability Matrix

```
REQ-id (spec.md) ─┬─ AC-id (acceptance criterion)
                  ├─ TASK-id (tasks.md, [P]?, file path)
                  ├─ TEST-id (test::case)  ← must FAIL before impl
                  ├─ CODE-ref (file:symbol)
                  └─ CI-evidence (run id, gate results, coverage)
```

Every row resolves end-to-end or `verify-spec` blocks. Orphan detection:
`verify_traceability()` in `src/ooagent/workflow/traceability.py`. Live
example: `specs/001-spec-driven-workflow-layer/`.

---

## 7. Command Integration (documentation only — no CLI wiring in this pass)

```
/init           → scaffold §0.1 structure for a downstream fork (this repo already has it).
/constitution   → project the constitution into constitution.md + constitution.py.
/specify        → spec.md: what & why, REQ/AC ids, edge/abuse cases. No stack.
/clarify        → resolve ambiguity; updates spec.md.
/plan           → plan.md: DIP stack + architecture + constitution-check.
/checklist      → quality + security checklist derived from constitution.
/tasks          → tasks.md: dependency-ordered, [P] markers, test-first.
/analyze        → read-only cross-artifact consistency check. Pre-implement gate.
/implement      → execute tasks under TDD; ledgered.
/verify         → run the §5 gate contract (.specify/gates/Makefile via CI).
/handoff        → README/scope-closure/RACI/change-enablement.
/support        → change records.
```

A real slash-command surface (wiring these into an agent harness) is a
future extension point — see §9 below, and CLAUDE.md §22's extension
protocol for the pattern to follow.

---

## 8. Composition with `OOAgent`

- `IDeliveryWorkflow` is a peer layer, not a `respond()` pipeline step —
  `core/agent.py` is untouched by this layer.
- An agent whose job *is* software delivery (e.g., a coding-assistant
  built on `OOAgent`) could compose `SpecDrivenWorkflow` as a collaborator
  the same way `ContextRegistry` holds an `IDomainContext` — that
  composition is left to the composing project, not prescribed here.
- Stack bindings live in `.specify/gates/Makefile` (DIP), never in
  `workflow/spec_driven.py`.
- On conflict between this layer and `IDomainContext` invariants,
  `CLAUDE.md`'s correctness-first precedence (§11) applies unchanged.

---

## 9. Anti-Patterns (forbidden — extends CLAUDE.md §21)

- Hardcoding any stack, tool, or vendor into `workflow/` or
  `sdd-gate.yml` (belongs in `.specify/gates/Makefile`).
- Implementing before `spec.md`/`plan.md`/`tasks.md` exist for a feature.
- Writing implementation code before its failing test (ARTICLE VI breach).
- `continue-on-error`/skip on any required gate.
- Merging with a red gate, an orphan requirement, or an untested
  acceptance criterion.
- Treating `verify-spec` findings as advisory rather than blocking.
- Invoking `IDeliveryWorkflow` methods from inside `core/agent.py`'s
  `respond()` — it is a peer layer, not a pipeline step.

---

## 10. Extension Points

To add a second `IDeliveryWorkflow` implementation (e.g. a lighter-weight
methodology for spikes): implement the ABC in a new
`src/ooagent/workflow/<name>.py`, ship its own conformance coverage
(mirror `tests/conformance/test_delivery_workflow.py` against the new
class), and register it wherever the composing project selects a
workflow — no edits to `core/protocols.py` required (OCP, per CLAUDE.md
§22's extension protocol).

---

## 11. Known Limitations

- No CLI/slash-command wiring in this pass — phases are documented and
  gate-checked, not yet invocable as literal commands.
- `sign`/`e2e`/`deploy`/`smoke`/`dast`/`verify-signature`/
  `alerting-probe` gates have `_optional` skip recipes, not real
  implementations — this project has no deployable service.
- `.specify/gates/Makefile` requires GNU Make; not verified locally on
  Windows dev environments without Make installed — verified in CI
  (`ubuntu-latest`) via `sdd-gate.yml`.
- CI-produced ledger entries are captured as a retained workflow artifact
  (`sdd-ledger-audit-${{ github.sha }}`, 30-day retention), not committed
  back to the repository; only local `make -f .specify/gates/Makefile
  ledger` runs append directly to the tracked working-tree
  `.specify/ledger/audit.log`.
