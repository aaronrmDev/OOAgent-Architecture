# Repo Process Maturity — Design

## Purpose

Sub-project F (the last) of the OOAgent improvement backlog (A: golden
path, PR #8; B: public API, PR #9; C: testing depth, PR #10;
D: observability & safety, PR #11; E: ecosystem & extension guides,
PR #12). The original proposal asked for CONTRIBUTING/ADRs, roadmap,
changelog, security policy, and a docs site.

Investigation found a different shape of gap than A-E: this repo already
has real process infrastructure (`.github/ISSUE_TEMPLATE/`,
`.github/PULL_REQUEST_TEMPLATE.md`, `CONTRIBUTORS.md` — a comprehensive
fork/PR/SDD/versioning/Gitflow/code-standards guide, a real `2026.06.01`
git tag, `pyproject.toml` at `2026.07.01`), but five specific standard
artifacts are **completely absent**: `SECURITY.md`, `CHANGELOG.md`,
`ROADMAP.md`, any ADR (Architecture Decision Record) directory, and a
docs site. Unlike A-E, this isn't "narrative guidance exists, one worked
example is missing" — these five files simply don't exist at all.

**Goal:** ship the three standard, low-risk, GitHub-convention files this
repo is missing (`SECURITY.md`, `CHANGELOG.md`, `ROADMAP.md`), plus a
minimal ADR process (directory, template, and 3 seed ADRs documenting
decisions already made and already scattered across `CLAUDE.md` and
`docs/superpowers/specs/`) — backfilling the record, not inventing new
decisions.

## Scope

**In scope:**

1. `SECURITY.md` — standard GitHub-recognized vulnerability-reporting
   policy. This repo already has real security-adjacent tooling worth
   pointing to (`CONTRIBUTORS.md`'s "13 AI Safety Guards" / AI Safety
   Gate, `DefaultSecurityPolicy` in `plugins/security/`, documented in
   `docs/EXTENDING.md`'s compatibility-contract section) — this file
   tells a reporter how to responsibly disclose a vulnerability, it does
   not re-document those existing tools.
2. `CHANGELOG.md` — seeded from real git history (the `2026.06.01`
   release commit, and the five sub-project merges A-E this session:
   PRs #8-#12), following Keep a Changelog format, matching this repo's
   `YYYY.MM.NN` versioning (CONTRIBUTORS.md's "Versioning" section).
   Establishes the file and its format; does not retroactively
   reconstruct every commit since repo inception.
3. `ROADMAP.md` — states what's shipped (A-E) and what's explicitly
   open (nothing currently planned beyond this backlog — stated
   honestly, not padded with speculative future work), linking to each
   sub-project's design spec for detail.
4. `docs/adr/` — an ADR directory with a template (`0000-template.md`,
   following the standard Michael Nygard ADR format: Title, Status,
   Context, Decision, Consequences) and **3 seed ADRs** documenting
   decisions already made and already visible elsewhere in this repo,
   backfilled rather than invented:
   - `0001-composition-over-inheritance-composition-root.md` — why
     `OOAgent` is a composition root injecting `ILLMClient`/
     `IDomainContext`/etc. rather than a class hierarchy (CLAUDE.md §1,
     §8a).
   - `0002-specdrivenworkflow-as-peer-layer-not-pipeline-step.md` — why
     `IDeliveryWorkflow`/`SpecDrivenWorkflow` is a 4th OOC layer
     orthogonal to `IDomainContext`, not a step inside `respond()`
     (CLAUDE.md §24, `docs/SPECDRIVEN.md`).
   - `0003-curated-public-api-barrel-not-wildcard-export.md` — why
     sub-project B's top-level `ooagent/__init__.py` is a curated
     17-name list instead of `from .core import *`
     (`docs/PUBLIC_API.md`, `docs/superpowers/specs/2026-07-06-public-api-stability-design.md`).
5. One new README "Go Deeper" line pointing at `docs/adr/` (the other
   three new files are root-level and GitHub-convention-discoverable on
   their own — `SECURITY.md`/`CHANGELOG.md` get automatic GitHub UI
   surfacing, so they don't need a README pointer the way a `docs/*.md`
   file does).

**Out of scope:**

- **A docs site** (mkdocs/Docusaurus/ReadTheDocs) — this needs a hosting
  decision, a nav structure across 8 existing `docs/*.md` files, and a
  CI publish workflow: a materially bigger, ongoing-maintenance
  commitment than a docs pass, the same reasoning that scoped out
  sub-project E's sample external packages. `ROADMAP.md` will name this
  as a known gap rather than silently omit it.
- **Renaming or replacing `CONTRIBUTORS.md` with `CONTRIBUTING.md`** —
  `CONTRIBUTORS.md` already comprehensively covers what a
  `CONTRIBUTING.md` would (fork/PR flow, SDD process, safety gate,
  versioning, Gitflow, what-you-can-contribute, code standards); a
  rename risks breaking existing inbound links (from README, PR
  template, etc.) for purely conventional-naming benefit. `ROADMAP.md`
  will note this file already serves that role.
- **Retroactively reconstructing a complete changelog back to repo
  inception** — `CHANGELOG.md` starts from the `2026.06.01` release and
  this session's A-E merges; earlier history is available via `git log`
  and is not duplicated into the file.
- **ADRs for every historical decision** — 3 seed ADRs for the most
  architecturally significant, already-documented decisions establish
  the process; retroactively writing an ADR for every design choice
  ever made in this repo is unbounded scope creep.
- **Any code change** — this entire sub-project is new root-level/docs
  files plus one README line. Nothing under `src/ooagent/` or `tests/`
  changes.

## `SECURITY.md` structure

```markdown
# Security Policy

## Reporting a Vulnerability
[how to report privately — GitHub private vulnerability reporting via
the repo's Security tab, or a direct contact if that's not enabled;
response-time expectation]

## Supported Versions
[which YYYY.MM.NN versions receive security fixes — current + prior
month, matching CONTRIBUTORS.md's versioning cadence]

## What Counts as a Security Issue Here
[pointer to the existing 13 AI Safety Guards / AI Safety Gate and
DefaultSecurityPolicy as the FRAMEWORK's existing security surface —
this file is about reporting a NEW vulnerability, not a description of
what's already built]
```

## `CHANGELOG.md` structure

```markdown
# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning
follows this project's YYYY.MM.NN scheme (CONTRIBUTORS.md).

## [Unreleased]
[sub-project F itself, once merged — process-maturity docs]

## [2026.07] — Improvement backlog A-E
### Added
- Golden-path README rewrite + examples/ folder (PR #8)
- Curated public API barrel export + docs/PUBLIC_API.md (PR #9)
- LLM adapter behavior-matrix tests + docs/TESTING.md (PR #10)
- Telemetry events on failure/tool/LLM-call paths + docs/OBSERVABILITY.md (PR #11)
- Worked CONTEXT.md example + docs/EXTENDING.md (PR #12)

## [2026.06.01]
[the existing tagged release — CI/CD, plugins, database layer, SecurityPlugin,
per that commit's own message]
```

## `ROADMAP.md` structure

```markdown
# Roadmap

## Shipped
[A-E, one line each, linking to each sub-project's design spec]

## Not currently planned
[docs site — named explicitly, per the out-of-scope reasoning above]

## How this roadmap is maintained
[updated at the end of each sub-project's finishing-a-development-branch
step, same discipline as this repo's memory-update practice]
```

## `docs/adr/` structure

```
docs/adr/
├── 0000-template.md         # Nygard format: Title, Status, Context, Decision, Consequences
├── 0001-composition-over-inheritance-composition-root.md
├── 0002-specdrivenworkflow-as-peer-layer-not-pipeline-step.md
└── 0003-curated-public-api-barrel-not-wildcard-export.md
```

Each seed ADR's Context/Decision/Consequences content is drawn from
already-written material (CLAUDE.md sections, existing design specs) —
this is a backfill/formalization pass, not new decision-making.

## Testing

Docs-only change — no new test files. Verification is:
- Every factual claim (git tag name, PR numbers, versioning scheme,
  which CLAUDE.md section documents which decision) checked against the
  real repo state at write time — same discipline as D/E, which each
  caught real drift during review.
- Full test suite + `ruff check .` + `mypy` run at the end to confirm
  zero regressions (a docs-only change should show zero diff in any of
  the three).

## Out-of-scope confirmation

No file under `src/ooagent/` or `tests/` changes. No docs-site tooling
(mkdocs config, CI publish workflow) is added. `CONTRIBUTORS.md` is read
but not renamed or restructured.

## Process note

Decided autonomously per the explicit "adecuate the best decisions ...
until finishing" AFK grant (reconfirmed with "Authorized" after
sub-project D's completion, and again implicitly by proceeding through E
without interactive checkpoints) — no interactive brainstorming
checkpoint for this sub-project, mirroring sub-projects D and E's
process. This is the last sub-project in the A-F backlog; once merged,
the full backlog from the original comprehensive improvement proposal is
complete.
