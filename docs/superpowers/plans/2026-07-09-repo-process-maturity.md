# Repo Process Maturity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the three standard root-level process files this repo is missing (`SECURITY.md`, `CHANGELOG.md`, `ROADMAP.md`) and a minimal ADR (Architecture Decision Record) process — a template plus 3 seed ADRs backfilling decisions already made and already documented elsewhere in the repo.

**Architecture:** Purely additive documentation. No file under `src/ooagent/` or `tests/` changes. Six new files total, one README line.

**Tech Stack:** Markdown only — no code, no new dependencies.

## Global Constraints

- No file under `src/ooagent/` or `tests/` is modified.
- Every factual claim (git tag name, PR numbers, this repo's actual versioning scheme, which CLAUDE.md section documents which decision) must be verified against the real repo state at write time, not assumed from this plan's prose — the same discipline sub-projects D and E applied, both of which caught real drift during review.
- The existing git tag is `2026.06.01`; `pyproject.toml`'s current `version` field is `2026.07.01` (verify both before writing `CHANGELOG.md`).
- `CONTRIBUTORS.md` is read but not renamed, restructured, or duplicated by a new `CONTRIBUTING.md` — `ROADMAP.md` notes it already serves that role.
- No docs-site tooling (mkdocs config, CI publish workflow, `docs/index.md` nav) is added — `ROADMAP.md` names this as a known, explicit gap rather than omitting it.
- ADR content (Context/Decision/Consequences) must be drawn from already-written material in this repo (`CLAUDE.md` sections, `docs/PUBLIC_API.md`, `docs/superpowers/specs/*`) — this is a backfill/formalization pass, not new decision-making. Do not invent rationale not already stated somewhere in the repo.

---

## File Structure

- Create `SECURITY.md` — vulnerability reporting policy (Task 1).
- Create `CHANGELOG.md` — Keep a Changelog format, seeded from real git/tag history (Task 1).
- Create `ROADMAP.md` — shipped (A-E) vs. not-currently-planned, honest and non-speculative (Task 1).
- Create `docs/adr/0000-template.md` — Nygard ADR format template (Task 2).
- Create `docs/adr/0001-composition-over-inheritance-composition-root.md` (Task 2).
- Create `docs/adr/0002-specdrivenworkflow-as-peer-layer-not-pipeline-step.md` (Task 2).
- Create `docs/adr/0003-curated-public-api-barrel-not-wildcard-export.md` (Task 2).
- Modify `README.md` — one new "Go Deeper" line pointing at `docs/adr/` (Task 2).

---

### Task 1: `SECURITY.md`, `CHANGELOG.md`, `ROADMAP.md`

**Files:**
- Create: `SECURITY.md`
- Create: `CHANGELOG.md`
- Create: `ROADMAP.md`

**Interfaces:**
- Consumes: nothing from other tasks (this task is self-contained).
- Produces: nothing consumed by Task 2 as a code interface; Task 2's README line and `ROADMAP.md`'s docs-site note are independent of this task's content.

- [ ] **Step 1: Verify the facts this task will cite**

Before writing, confirm each of these against the real repo (already
verified while writing this plan — re-confirm, since the implementer sees
only this task):
- `git tag` lists exactly one tag: `2026.06.01`.
- `git log --oneline --merges -3` shows the release commit message
  `release: 2026.06.01 — CI/CD, plugins, database layer, SecurityPlugin`.
- `pyproject.toml`'s `[project]` section has `version = "2026.07.01"`.
- `CONTRIBUTORS.md`'s "Versioning" section documents the `YYYY.MM.NN`
  scheme (4-digit year, 2-digit month, 2-digit sequential build).
- `CONTRIBUTORS.md` mentions "13 AI Safety Guards" and an AI Safety Gate
  (`scripts/ai-safety-gate.sh`).
- `src/ooagent/plugins/security/policy_engine.py` defines
  `DefaultSecurityPolicy` (already documented in `docs/EXTENDING.md`'s
  compatibility-contract section, sub-project E).
- The five sub-projects already shipped this backlog, in order, with
  their PR numbers: A (golden path, PR #8), B (public API, PR #9),
  C (testing depth, PR #10), D (observability & safety, PR #11),
  E (ecosystem & extension guides, PR #12).

- [ ] **Step 2: Create `SECURITY.md`**

```markdown
# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in OOAgent, please report it
privately rather than opening a public issue:

1. Use GitHub's [private vulnerability reporting](https://github.com/aaronrmDev/OOAgent-Architecture/security/advisories/new)
   feature (Security tab → Report a vulnerability) if enabled for this
   repository.
2. If private reporting isn't available, open an issue with minimal
   detail (do not include exploit specifics) and request a private
   channel.

We aim to acknowledge reports within 5 business days and to provide a
remediation timeline once the report is triaged.

## Supported Versions

This project uses `YYYY.MM.NN` versioning (see `CONTRIBUTORS.md`).
Security fixes are backported to the current and immediately prior
month's release. Older releases are not maintained.

## What Counts as a Security Issue Here

This framework already ships real security-adjacent tooling as part of
its normal architecture, not as a response to this policy:

- **AI Safety Gate** — 13 automated guards (`scripts/ai-safety-gate.sh`)
  that every contribution must pass before merge (see `CONTRIBUTORS.md`).
- **`DefaultSecurityPolicy`** (`src/ooagent/plugins/security/`) — prompt-
  injection detection, PII-warning logging, rate limiting, access
  control, and output validation for any `ITool` wrapped in
  `SecureToolWrapper` (see `docs/EXTENDING.md`'s compatibility-contract
  section for exactly what this does and does not cover today).

This policy is about **reporting a new vulnerability you've found** —
a gap in the framework's own code, a bypass of the AI Safety Gate, or a
flaw in `DefaultSecurityPolicy`'s checks — not a description of what's
already built (that's `docs/EXTENDING.md` and `CONTRIBUTORS.md`'s job).
```

- [ ] **Step 3: Create `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning
follows this project's `YYYY.MM.NN` scheme (see `CONTRIBUTORS.md`).

## [Unreleased]

### Added
- `SECURITY.md`, `CHANGELOG.md`, `ROADMAP.md`, and `docs/adr/` — repo
  process maturity (backlog sub-project F).

## [2026.07] — Improvement backlog A-E

### Added
- Golden-path README rewrite, `examples/` folder, `docs/ARCHITECTURE.md`
  (backlog sub-project A, PR #8).
- Curated top-level public API barrel export, `docs/PUBLIC_API.md`
  (backlog sub-project B, PR #9).
- LLM adapter behavior-matrix tests, `docs/TESTING.md` (backlog
  sub-project C, PR #10).
- Telemetry events on previously-silent failure/tool/LLM-call paths,
  `docs/OBSERVABILITY.md` (backlog sub-project D, PR #11).
- Worked `CONTEXT.md` example, `docs/EXTENDING.md` (backlog sub-project
  E, PR #12).

## [2026.06.01]

### Added
- CI/CD pipeline, plugin system, database layer, `SecurityPlugin`.
```

- [ ] **Step 4: Create `ROADMAP.md`**

```markdown
# Roadmap

## Shipped

A comprehensive improvement backlog (positioning, onboarding,
architecture clarity, API surface, testing depth, observability,
ecosystem/extension guides, repo process maturity) was decomposed into
six sub-projects, A through F:

- **A. Golden Path & Positioning** — README rewrite, `examples/` folder.
  [Design spec](docs/superpowers/specs/2026-07-06-golden-path-examples-design.md).
- **B. Public API & Stability Contract** — curated top-level barrel
  export, `docs/PUBLIC_API.md`.
  [Design spec](docs/superpowers/specs/2026-07-06-public-api-stability-design.md).
- **C. Testing & Reliability Depth** — LLM adapter behavior-matrix
  tests, `docs/TESTING.md`.
  [Design spec](docs/superpowers/specs/2026-07-06-testing-reliability-depth-design.md).
- **D. Observability & Safety** — telemetry events on previously-silent
  failure paths, `docs/OBSERVABILITY.md`.
  [Design spec](docs/superpowers/specs/2026-07-08-observability-safety-design.md).
- **E. Ecosystem & Extension Guides** — worked `CONTEXT.md` example,
  `docs/EXTENDING.md`.
  [Design spec](docs/superpowers/specs/2026-07-09-ecosystem-extension-guides-design.md).
- **F. Repo Process Maturity** (this sub-project) — `SECURITY.md`,
  `CHANGELOG.md`, `ROADMAP.md`, `docs/adr/`.
  [Design spec](docs/superpowers/specs/2026-07-09-repo-process-maturity-design.md).

## Not currently planned

- **A hosted docs site** (mkdocs, Docusaurus, or similar) — this repo's
  eight `docs/*.md` files are readable directly on GitHub; building and
  maintaining a generated site with its own hosting and CI publish step
  is a real gap, named here rather than silently omitted, but is not
  currently planned work.
- **A separate `CONTRIBUTING.md`** — `CONTRIBUTORS.md` already
  comprehensively covers the fork/PR flow, SDD process, AI Safety Gate,
  versioning, Gitflow, and code standards a `CONTRIBUTING.md` would;
  there is no plan to duplicate or rename it.

## How this roadmap is maintained

Updated at the end of each sub-project's finishing-a-development-branch
step — the same "update the record when the work actually lands"
discipline this project applies to its own memory/process notes.
```

- [ ] **Step 5: Verify the full suite still passes**

Run (with the `PYTHONPATH` override this repo's shared-venv worktree
setup requires — see this plan's Global Constraints and sub-projects D
and E's plans for why):
`f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS, identical counts to before this task (docs-only change).

- [ ] **Step 6: Lint check**

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add SECURITY.md CHANGELOG.md ROADMAP.md
git commit -m "docs: add SECURITY.md, CHANGELOG.md, ROADMAP.md"
```

---

### Task 2: `docs/adr/` — ADR process + 3 seed ADRs + README link

**Files:**
- Create: `docs/adr/0000-template.md`
- Create: `docs/adr/0001-composition-over-inheritance-composition-root.md`
- Create: `docs/adr/0002-specdrivenworkflow-as-peer-layer-not-pipeline-step.md`
- Create: `docs/adr/0003-curated-public-api-barrel-not-wildcard-export.md`
- Modify: `README.md` (Go Deeper section — one new line)

**Interfaces:**
- Consumes: nothing from Task 1 as a code interface.
- Produces: nothing consumed by other tasks (final task in this plan).

- [ ] **Step 1: Verify the facts this task will cite**

Before writing, confirm each of these against the real repo (already
verified while writing this plan — re-confirm, since the implementer sees
only this task):
- CLAUDE.md §1 (Class Hierarchy) shows `OOAgent` composing (not
  inheriting) `ILLMClient`, `ContextRegistry`, `ToolRegistry`,
  `PluginRegistry`, `SessionState`, `LifecycleManager`,
  `ResponsePipeline`, `SolverDispatcher`, `ArtifactFactory`,
  `ConstraintEngine`, `ProvenanceTracker`, `TelemetryProvider`,
  `ResponseDecorator` — all injected via constructor.
- CLAUDE.md §1 states: "Composition over inheritance. No god-class. Each
  collaborator owns exactly one concern. `OOAgent` is a **composition
  root**, not a monolith."
- CLAUDE.md §8a states: "prefer composition + injection over
  inheritance. Subclass only when you need to override a protected
  Template Method step."
- CLAUDE.md §24 states `IDeliveryWorkflow` is "A fourth OOC layer,
  orthogonal to `IDomainContext`" and that "`core/agent.py`'s
  `respond()` Template Method is untouched; this layer is a peer, never
  a pipeline step."
- CLAUDE.md §24 names the sole implementation `SpecDrivenWorkflow`
  (`src/ooagent/workflow/spec_driven.py`), and states gate *execution*
  is deliberately not that class's concern — `.specify/gates/Makefile`
  is the DIP seam.
- `docs/PUBLIC_API.md`'s "Core primitives" table lists exactly 17 names;
  its "Stability contract" section states a breaking change to any core
  primitive requires a major version bump, while advanced-tier names may
  move between modules across minor versions.
- `docs/superpowers/specs/2026-07-06-public-api-stability-design.md`
  documents that sub-project B's scope was narrowed specifically to
  avoid a wildcard `from .core import *` re-export, in favor of a
  curated list — read this file's actual content for the exact
  reasoning before writing the ADR (do not invent reasoning not present
  in that file).

- [ ] **Step 2: Create `docs/adr/0000-template.md`**

```markdown
# ADR-NNNN: [short title]

## Status

[Proposed | Accepted | Superseded by ADR-NNNN | Deprecated]

## Context

[What forces are at play — technical, business, architectural constraints.
State the problem being solved, not the solution.]

## Decision

[The change being made, stated in active voice: "We will ..."]

## Consequences

[What becomes easier or harder as a result. Include trade-offs honestly —
an ADR that only lists benefits isn't a real decision record.]
```

- [ ] **Step 3: Create `docs/adr/0001-composition-over-inheritance-composition-root.md`**

```markdown
# ADR-0001: OOAgent is a composition root, not a class hierarchy

## Status

Accepted

## Context

An AI agent framework needs to combine many independent concerns per
turn: LLM backend selection, domain-context resolution, tool execution,
plugin extension points, session/FSM state, response validation,
artifact building, and telemetry. A natural first instinct is to model
this as a deep inheritance hierarchy — a base `Agent` class, subclassed
per capability (`ToolUsingAgent`, `ContextAwareAgent`,
`ObservableAgent`, ...) — but multiple inheritance or deep single
inheritance chains make it hard to add a new capability (a new LLM
vendor, a new domain, a new plugin) without touching or subclassing
existing code, violating the Open/Closed Principle.

## Decision

`OOAgent` (`src/ooagent/core/agent.py`) is a **composition root**: it
composes, via constructor injection, an `ILLMClient`, a
`ContextRegistry`, a `ToolRegistry`, a `PluginRegistry`, a
`SessionState`, a `LifecycleManager`, a `ResponsePipeline`, a
`SolverDispatcher`, an `ArtifactFactory`, a `ConstraintEngine`, a
`ProvenanceTracker`, a `TelemetryProvider`, and a `ResponseDecorator` —
each collaborator owning exactly one concern (CLAUDE.md §1). The class
hierarchy above `OOAgent` (`IAgent` → `AbstractAgent` → `LLMAgent` →
`OOAgent`) is shallow and exists only to layer in the minimal state each
level actually needs (an `agent_id`, then an `ILLMClient` reference) —
not to carry behavior via subclassing. Extension happens by injecting a
new implementation of an interface (a new `ILLMClient`, a new
`IDomainContext`, a new `ITool`, a new `IPlugin`), never by subclassing
`OOAgent` itself except to override a single protected Template Method
step (CLAUDE.md §8a).

## Consequences

Adding a new LLM vendor, domain, tool, or plugin requires zero edits to
`core/` — each is a new class implementing an existing interface,
registered at construction time (CLAUDE.md §22's Extension Protocol).
Testing is straightforward: any collaborator can be replaced with a test
double independently (`StubLLMClient`, `NullContext`, `NullTelemetry`).
The cost is more constructor parameters on `OOAgent.__init__` as new
collaborators are added, and a discipline requirement — no collaborator
may reach into another's internals (CLAUDE.md §21's "Plugin side-effects
on agent internals" anti-pattern) — that has to be enforced by review
and interface design (`IPlugin` accepting only `IAgent`, not `OOAgent`),
not by the type system alone.
```

- [ ] **Step 4: Create `docs/adr/0002-specdrivenworkflow-as-peer-layer-not-pipeline-step.md`**

```markdown
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
```

- [ ] **Step 5: Create `docs/adr/0003-curated-public-api-barrel-not-wildcard-export.md`**

Read `docs/superpowers/specs/2026-07-06-public-api-stability-design.md`
first and draw this ADR's Context/Decision/Consequences from that file's
actual stated reasoning (do not invent reasoning not present there) —
the Context/Decision/Consequences text below is a starting point; adjust
wording to match what that design spec actually says if it differs from
this paraphrase, but keep the same structure and conclusion (a curated
17-name list, not a wildcard re-export).

```markdown
# ADR-0003: `ooagent`'s top-level barrel export is a curated list, not a wildcard re-export

## Status

Accepted

## Context

Every `ooagent` sub-package already had its own `__all__` export and
`ooagent.core` already re-exported everything from `core/protocols.py`
by the time this decision was made — but the bare top-level
`ooagent/__init__.py` had no curated surface at all, forcing every
consumer to import from `ooagent.core.protocols` (or deeper submodules)
directly, with no signal about which of those names are the primary
integration surface versus implementation-adjacent detail. The obvious
shortcut — `from .core import *` at the top level — would have made
every advanced/internal name (`ArtifactFactory`, `ConstraintEngine`,
`SessionState`, `CircuitBreaker`, every advanced-only ABC) equally
prominent as the handful of names an application author actually needs
day to day, and would have made the stability contract (CLAUDE.md §18)
ambiguous — a wildcard export gives no way to say "these 17 names are
semver-stable, everything else may move."

## Decision

`ooagent/__init__.py` exports a curated, explicit, non-wildcard list of
17 names (`OOAgent`, `AgentConfig`, `Query`, `Artifact`, `ILLMClient`,
`IDomainContext`, `ITool`, `IPlugin`, `ContextRegistry`, `ToolRegistry`,
`OOAgentError`, and the 6 concrete exception subclasses) — documented in
full in `docs/PUBLIC_API.md`'s "Core primitives" table. Everything else
remains reachable via `ooagent.core`, `ooagent.adapters.*`,
`ooagent.contexts`, `ooagent.plugins.*`, `ooagent.telemetry`, or
`ooagent.workflow` — the "Advanced surface," per the same document.

## Consequences

The core-primitives list carries a real stability promise (CLAUDE.md
§18: a breaking change to any of the 17 names requires a major version
bump), while the advanced surface can be reorganized across minor
versions without a deprecation cycle. New application authors get an
unambiguous, small starting import list (`from ooagent import OOAgent,
AgentConfig, Query, ...`) instead of needing to already know the package
layout. The cost is that this curated list must be manually maintained —
a new core-tier addition means an explicit edit to
`ooagent/__init__.py`'s list plus `docs/PUBLIC_API.md`'s table, not an
automatic pickup the way a wildcard export would provide.
```

- [ ] **Step 6: Link from README**

Read the current `README.md` "Go Deeper" section first (it should match
sub-project E's ending state — a `docs/OBSERVABILITY.md` line followed by
a `docs/EXTENDING.md` line, per that sub-project's plan). Insert one new
line immediately after the `docs/EXTENDING.md` line, before the
`CLAUDE.md` line:

```markdown
- [`docs/adr/`](docs/adr/0000-template.md) — architecture decision records: why the composition root, why SpecDrivenWorkflow is a peer layer, why the curated public API barrel
```

If the actual "Go Deeper" section you find differs from this assumed
position (e.g. a different line order), insert the new line immediately
before the `CLAUDE.md` line rather than forcing an exact match — the
requirement is one new line near the end of the list, not a byte-
identical block.

- [ ] **Step 7: Verify the full suite still passes**

Run:
`f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS, identical counts to before this task.

- [ ] **Step 8: Lint check**

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 9: Commit**

```bash
git add docs/adr/ README.md
git commit -m "docs: add docs/adr/ (ADR template + 3 seed ADRs), link from README"
```

---

## Self-Review

**Spec coverage:**
- `SECURITY.md`, `CHANGELOG.md`, `ROADMAP.md` — Task 1. ✅
- `docs/adr/` template + 3 seed ADRs (composition root, SpecDrivenWorkflow
  peer layer, curated public API barrel) — Task 2. ✅
- README link — Task 2, Step 6. ✅
- Out-of-scope items (docs site, `CONTRIBUTING.md` rename/duplication,
  retroactive full changelog, ADRs for every historical decision, any
  `src/`/`tests/` change) — none touched by either task; `ROADMAP.md`
  and this plan's own out-of-scope notes name the docs-site and
  `CONTRIBUTING.md` gaps explicitly rather than omitting them. ✅

**Placeholder scan:** no "TBD"/"TODO"/vague-instruction steps; every step
has complete, verified content — except ADR-0003, which explicitly
instructs the implementer to verify against
`docs/superpowers/specs/2026-07-06-public-api-stability-design.md`'s
actual text rather than trusting this plan's paraphrase alone. That is a
deliberate verification instruction, not a placeholder — the fallback
content itself is complete and usable if the spec file confirms it.

**Type consistency:** not applicable (docs-only plan, no code interfaces).
