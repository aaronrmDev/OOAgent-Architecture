# 002 — Release Workflow Git Identity Fix

## Requirements

- **REQ-1**: `.github/workflows/release.yml`'s "Create git tag" step configures a git committer identity before creating the annotated release tag.
  - **AC-1**: The step's script contains `git config user.name "github-actions[bot]"` and `git config user.email "github-actions[bot]@users.noreply.github.com"`, both appearing before the `git tag -a` command in the same step.

## User Stories

As a maintainer cutting an OOAgent release, I want the automated
`release.yml` workflow to create the version tag and GitHub Release
without manual intervention, so that a release doesn't require an
ad-hoc git/`gh` workaround every time.

## Background (why this spec exists retroactively)

The v2026.07.01 release (PR #14, merged to `master` 2026-07-10) exposed
this defect live: the "Create GitHub Release" job's "Create git tag"
step failed with `fatal: empty ident name (for <runner@...>) not
allowed` — GitHub Actions runners ship with no default
`git config user.name`/`user.email`, and `git tag -a` (an *annotated*
tag, which creates a real tag object with a committer) refuses to run
without one. The `validate-version`, `full-suite`, and `build-release`
jobs all passed; only the tag-creation step failed.

The fix (two `git config` lines, commit `acf3e4d`) was applied directly
to unblock the release — the tag and GitHub Release for v2026.07.01 were
created manually using the same identity values, and the fix was pushed
to `develop` the same day. This spec formalizes that already-shipped fix
retroactively per this repo's `SpecDrivenWorkflow` methodology
(`docs/SPECDRIVEN.md`), so it carries the same spec → task → test →
code → CI-evidence traceability as forward-planned work, per ARTICLE
VIII. See `plan.md`'s Constitution Check for the honest TDD-ordering
note this implies.

## Success Criteria

REQ-1 holds, verified by its paired test (see `tasks.md`), and
`bash scripts/sdd-verify-spec.sh` exits 0 against this
`specs/002-release-workflow-git-identity/` directory.

## Edge Cases & Abuse Cases

- A future edit to `release.yml` removes the two `git config` lines
  (e.g. during an unrelated refactor of the "Create git tag" step) —
  the paired test must fail, catching the regression before it reaches
  a real release.
- A future edit reorders the lines so `git tag -a` runs before the
  `git config` calls — the test asserts ordering (not just presence),
  so this is caught too.
- A future contributor changes the bot identity strings (e.g. to a
  different bot account) — this is a legitimate change, not a defect;
  the test would need updating alongside it, same as any other
  behavior-defining assertion.

## Out of Scope

- The `publish-npm` job's `uv publish` step (a pre-existing, differently
  named misnomer — it publishes to PyPI, not npm) and whether a
  `PYPI_TOKEN`/`UV_PUBLISH_TOKEN` secret should be configured — no
  secret is configured today, so that job fails harmlessly; not this
  spec's concern.
- Re-running the v2026.07.01 release's automated tag/release job now
  that the fix exists — that release is already tagged and published
  (created manually, verified working); this spec exists so the *next*
  release doesn't need the same manual workaround.
- Broader git-identity conventions across the other 5 Gitflow workflows
  (`ci-core.yml`, `develop-integration.yml`, `feature-pr.yml`,
  `hotfix.yml`, `ci-autofix.yml`) — none of them create git tag objects,
  so none of them hit this failure mode; only `release.yml` needed this
  fix. `ci-autofix.yml` already configures a git identity for a
  different reason (committing autofix changes) using different values
  (`ci-autofix[bot]` / `ci-autofix@ooagent.dev`, vs. this fix's
  `github-actions[bot]` / `github-actions[bot]@users.noreply.github.com`)
  — reconciling the two into one shared identity is a possible future
  cleanup, not part of this spec.
