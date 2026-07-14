# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning
follows this project's `YYYY.MM.NN` scheme (see `CONTRIBUTORS.md`).

## [Unreleased]

## [2026.07.03] — Zero-gaps audit, MCP server, TypeScript cleanup

### Added
- `src/ooagent/mcp/` — OOAgent as an MCP (Model Context Protocol)
  server: a `respond` tool wrapping the full `OOAgent.respond()`
  pipeline, a `contexts://list` resource, env-var-driven LLM backend
  selection, and the `ooagent-mcp` console script (PR #15). See
  `docs/MCP.md`.
- `Invariant.check` — an optional predicate callable on `Invariant`,
  letting `ConstraintEngine` genuinely enforce domain/generic
  invariants instead of always passing (PR #17).
- `ILLMClient.ping()` — a health-probe hook (default `True`, non-breaking)
  that `LifecycleManager.health_check()` now actually calls (PR #17).
- `IPlugin.self_check()` — a health-probe hook (default `True`,
  non-breaking) that `PluginRegistry.verify()` now actually calls
  (PR #17).
- Real timeout enforcement via `asyncio.wait_for` for `turn_timeout_ms`,
  `tool_timeout_ms`, `specialist_timeout_ms`, and
  `orchestration_timeout_ms` — the latter two newly wired into
  `MultiAgentOrchestrator`, which previously had none at all (PR #17).
- `scan_spec_directory`/`scan_specs_root` — parse real
  `specs/<slug>/spec.md`+`tasks.md` into `TraceabilityEntry` data,
  proven against this repo's own specs, replacing a traceability module
  that was only ever exercised against synthetic fixtures (PR #17).
- `tests/conformance/test_plugin.py` — an `IPlugin` conformance suite
  (32 tests across all 8 concrete plugins); `HttpFetchTool` conformance
  coverage in `tests/conformance/test_tool.py` (PR #17).
- The 4 previously-skipped `IAgent` conformance tests now run real
  assertions (PR #17).

### Changed
- `mypy --strict`'s scope widened from `src/ooagent` only to
  `src/ooagent` + `tests/` + `examples/` (114 files) — confirmed the
  wider scope does not weaken production-code strictness (PR #17).
- `specs/001-spec-driven-workflow-layer/tasks.md`'s checkboxes now
  correctly show all 6 tasks as complete (PR #17).
- `SessionState` memento eviction is real LRU (tracks access via
  `restore()`), not FIFO (PR #17).
- Removed the unreachable `DEGRADED` FSM state — never entered by any
  code path and absent from the CLAUDE.md §12 diagram; the separate
  `HealthStatus` "degraded" value is unaffected (PR #17).
- All remaining TypeScript-era artifacts removed: the dead
  `packages/{autogen-tools,copilot-extension,mcp-server}/` TS
  sub-packages (untouched since a single initial commit;
  `mcp-server` fully superseded by `src/ooagent/mcp/`), stale
  auto-generated skill docs describing this as "a TypeScript codebase,"
  a misnamed `release.yml` `publish-npm` job (renamed `publish-pypi` —
  it always published to PyPI via `uv publish`), and a `ci-core.yml`
  job mislabeled "TypeScript Build" (PR #18).

### Fixed
- `ConstraintEngine._assert` was a permanent no-op — invariants were
  never enforced despite being the architecture's central safety claim.
  Now raises `ConstraintViolationError` on `severity="error"` check
  failures (PR #17).
- `OtelTelemetryProvider.gauge()` silently discarded its value instead
  of reporting it — now registers a real observable-gauge callback
  (PR #17).
- `DateTimeTool` mislabeled non-UTC timestamps with a false `"Z"` (UTC)
  suffix — now emits the real numeric offset (PR #17).
- `tests/mcp/test_config.py`'s vendor-construction tests only asserted
  `isinstance`; now assert the API key/model actually wired through
  (PR #17).
- `.gitignore` no longer excludes `node_modules/` after the TypeScript
  cleanup (PR #18) — restored; the entry is tooling-agnostic (e.g.
  VSCode's TypeScript IntelliSense can recreate the directory
  regardless of whether the project uses TS source) and should never
  have been removed.

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
