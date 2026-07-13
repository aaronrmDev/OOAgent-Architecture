# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning
follows this project's `YYYY.MM.NN` scheme (see `CONTRIBUTORS.md`).

## [Unreleased]

### Added
- `src/ooagent/mcp/` — OOAgent as an MCP (Model Context Protocol)
  server: a `respond` tool wrapping the full `OOAgent.respond()`
  pipeline, a `contexts://list` resource, env-var-driven LLM backend
  selection, and the `ooagent-mcp` console script (PR #15). See
  `docs/MCP.md`.

## [2026.07.01] — Improvement backlog A-F

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
- `SECURITY.md`, `CHANGELOG.md`, `ROADMAP.md`, and `docs/adr/` — repo
  process maturity (backlog sub-project F, PR #13).

### Fixed
- `release.yml`'s "Create git tag" step failed on this very release with
  `fatal: empty ident name` (no git identity configured on the CI
  runner) — fixed for future releases; this release's tag/GitHub Release
  were created manually. See `specs/002-release-workflow-git-identity/`.

## [2026.06.01]

### Added
- CI/CD pipeline, plugin system, database layer, `SecurityPlugin`.
