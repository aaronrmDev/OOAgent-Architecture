# 002 — Plan

## Stack (DIP injection point)

No new stack — this touches only an existing GitHub Actions workflow
file (YAML/bash) and adds one `pytest` test file, using this repo's
existing test stack (`docs/superpowers/specs/2026-07-04-python-port-design.md`).

## Architecture

`.github/workflows/release.yml`'s "Create git tag" step gains two
`git config` lines (hardcoded, non-secret literal identity values) ahead
of its existing `git tag -a`/`git push origin` sequence. No new
collaborator, no new interface — this is a two-line change to an
existing CI step, not a design change. The paired test
(`tests/workflow/test_release_workflow_git_identity.py`) follows the
existing structural-check pattern already used for
`tests/workflow/test_gate_makefile.py`: read the workflow file as text,
locate the target step, assert on ordering — real execution of the
workflow only happens on GitHub Actions (`ubuntu-latest`), same
limitation this repo's other workflow-structure tests already document.

## Constitution Check

- **ARTICLE I (Form)**: the two added lines are plain, typed-by-context
  shell commands with no filler; the paired test is a normal typed
  Python function.
- **ARTICLE II (Security)**: no new attack surface. Both added values
  are static literals (a conventional bot username, its public
  GitHub-provided noreply email) — no secret handling, no user input,
  no change to `GITHUB_TOKEN` usage or the job's `permissions:` block.
  Confirmed via a dedicated `/security-review` pass on this exact diff
  before this spec was written: zero findings.
- **ARTICLE III (Governance)**: this spec, plus a ledger entry appended
  to `.specify/ledger/audit.log` after running the applicable gates
  locally (see Gate Recipes Touched below), is the audit record.
- **ARTICLE IV (Lifecycle)**: the code fix (commit `acf3e4d`) already
  merged to `develop` via the standard Gitflow push-with-confirmation
  process used throughout this session; this spec is retroactive
  documentation of that same change, not a new code change.
- **ARTICLE V (Architecture)**: no pattern applies beyond the existing
  Adapter/Bridge framing already established for this repo's CI gate
  structure (`.specify/gates/Makefile` as the DIP seam) — this fix
  doesn't touch that seam, only a Gitflow-specific workflow step.
- **ARTICLE VI (Testing, NON-NEGOTIABLE) — honest deviation note**: the
  code fix (`acf3e4d`) was applied and merged *before* this spec and its
  paired test existed, because it was a live-incident fix unblocking an
  in-progress release, not forward-planned feature work. This spec
  formalizes it after the fact, which means the test was **not**
  chronologically test-first for the original fix. What *is* true
  test-first, starting now: the test exists, is real (not a stub), fails
  against the pre-fix file content (verified by inspection — the pre-fix
  step had no `git config` lines at all, so the assertions'
  `assert ... != -1` checks would fail), and passes against the current
  fixed file. Any future edit to this step is now genuinely gated by a
  failing-first test, closing the loop for regressions even though the
  original fix predates it. This is the same honesty-over-fabrication
  standard applied to `docs/OBSERVABILITY.md` and `docs/adr/0003-*` in
  the immediately preceding backlog work.
- **ARTICLE VII (Zero Defects)**: this feature adds one new test file
  with 2 test functions; it does not lower the existing coverage floor
  (structural workflow-file assertions aren't in the `src/` coverage
  measurement, matching `test_gate_makefile.py`'s precedent).
- **ARTICLE VIII (Traceability)**: this document plus `tasks.md` is
  REQ-1's evidence chain: REQ-1 → AC-1 → TASK-1 → TEST-1 →
  `.github/workflows/release.yml:125-126` → this session's local gate
  run (see Gate Recipes Touched).

## Gate Recipes Touched

`verify-spec` (new — this directory), `test` (new test file added to
the existing `pytest tests/` run), `typecheck`/`lint`/`format-check`
(already existed via `ci-core.yml`; re-run locally against the new test
file), `ledger` (new entry appended locally, since CI-produced ledger
entries are artifact-only per `docs/SPECDRIVEN.md` §11's documented
limitation, not committed back to the repo).
