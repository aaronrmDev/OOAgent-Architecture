# Python Port of OOAgent — Design

## Purpose

Replace the TypeScript implementation of OOAgent with a Python implementation.
Python becomes the sole language for the architecture defined in `CLAUDE.md`.
This is the first of two sequential sub-projects; the second
(`SpecDrivenWorkflow` / `IDeliveryWorkflow`, a fourth OOC layer with its own
CLAUDE.md-equivalent spec, CI orchestrator, and gate Makefile) is designed and
implemented after this one lands.

## Scope

**In scope** — full parity port of the core architecture (~5,600 lines):

- `core/` — protocols, agent, state, pipeline, artifacts, registry, lifecycle, orchestrator
- `adapters/llm/` — anthropic, openai, gemini, ollama, caching_proxy
- `adapters/tools/` — base, adapter
- `adapters/data/` — datastore-plugin, in-memory-store, normalizer, protocols, validator
- `contexts/` — null_context
- `plugins/` — audit, base-plugin, cache, logging, opentelemetry, rate-limit, scope-guard, security (incl. policy-engine, secure-tool-wrapper), tool-kit (calculator, datetime, http-fetch)
- `telemetry/` — console, null_telemetry, otel
- `testing/` — conformance suite, fixtures, stub_llm_client, null_context re-export
- `scripts/` — ai-safety-gate.sh, conformance-check.sh, version-check.sh (rewritten for Python)
- `.github/workflows/*.yml` — 6 workflows, steps swapped from npm/tsc/jest to uv/ruff/mypy/pytest
- `CLAUDE.md`, `README.md`, `CONTRIBUTORS.md` — code samples and commands updated to Python

**Out of scope** (deferred, each needs its own scoped decision later):

- `packages/autogen-tools` — wraps `ITool` for Microsoft AutoGen (itself a Python framework)
- `packages/copilot-extension` — GitHub Copilot Extensions API server (Node-oriented API)
- `packages/mcp-server` — MCP server exposing OOAgent tools (has its own Python SDK to evaluate)

**Deferred to phase 3** (post-port hardening, not part of this port):

- Fleshing out the 5 conformance tests currently marked `TODO`/stub — ported as-is (`pytest.mark.skip`)
- Gitflow branching/release ceremony weight — separate discussion, unrelated to language
- Adding a real (non-Null) `IDomainContext` to prove the architecture end-to-end

## Package layout

```
src/ooagent/
  core/
    protocols.py    agent.py       state.py
    pipeline.py     artifacts.py   registry.py
    lifecycle.py    orchestrator.py
  adapters/
    llm/
      anthropic.py  caching_proxy.py  gemini.py  ollama.py  openai.py
    tools/
      base.py  adapter.py
    data/
      datastore_plugin.py  in_memory_store.py  normalizer.py  protocols.py  validator.py
  contexts/
    null_context.py
  plugins/
    audit/  base_plugin.py  cache/  logging/  opentelemetry/  rate_limit/  scope_guard/  security/  tool_kit/
  telemetry/
    console.py  null_telemetry.py  otel.py
tests/
  conformance/
    test_agent.py  test_context.py  test_llm_client.py  test_tool.py
  fixtures.py  stub_llm_client.py  null_context.py
```

`src/` layout (not flat) so the installed package can't accidentally import
the test tree. It's a 1:1 file-for-file mapping from the TS tree — including
`plugins/logging/` and `plugins/opentelemetry/` as nested subpackage names;
Python 3's absolute-import semantics mean a subpackage named `logging`
nested under `ooagent.plugins` never shadows the stdlib `logging` module, so
no renaming is needed there.

## Core contracts

- `core/protocols.py` stays dependency-free: stdlib only (`abc`, `typing`,
  `dataclasses`, `enum`) — preserves the "zero runtime dependencies" invariant
  from `CLAUDE.md` §7.
- Every `I*` interface (`IAgent`, `ILLMClient`, `IDomainContext`, `ISolver`,
  `ITool`, `IPlugin`, `ILifecycle`, `ISessionState`, `ITelemetryProvider`,
  `IArtifactFactory`, `IOrchestrator`) becomes an `abc.ABC` with
  `@abstractmethod` methods. Matches the doc's explicit-inheritance GoF
  framing (Template Method, Abstract Factory) and gives runtime enforcement:
  instantiating an incomplete subclass raises `TypeError` immediately.
- Value objects (`CompletionRequest`, `CompletionResponse`, `CompletionChunk`,
  `Solution`, `Artifact`, `Query`, `Term`, `ProblemClass`, `InputSpec`,
  `ArtifactPolicy`, `Invariant`, `AntiPattern`, `HealthStatus`,
  `PluginContributions`) become frozen `@dataclass`.
- Generics (`IAgent[TQuery, TResponse]`) use `typing.Generic` with `TypeVar`.

## Async & error model

- `async def` + `AsyncIterator` throughout — direct analogue of
  `Promise`/`AsyncIterator`, no thread pools, no sync-wrapper shims.
- Exceptions (`ConstraintViolation`, `FSMViolation`, `ToolExecutionError`,
  `TokenLimitError`, `LifecycleError`) form a small hierarchy under one
  `OOAgentError(Exception)` base — organizational addition only, no behavior
  change from the TS version (which had no common base).

## Tooling & CI

- `pyproject.toml` managed by `uv`, Python ≥3.11.
- `ruff` for lint + format (replaces eslint/prettier).
- `mypy --strict` for type checking (replaces `tsc --strict`).
- `pytest` for tests (replaces `node --test`).
- `scripts/ai-safety-gate.sh` (517 lines, the "10 AI Safety Guards") — checks
  reworked to scan `.py` sources instead of `.ts`.
- `scripts/version-check.sh` — reads the version from `pyproject.toml`
  instead of `package.json`; `YYYY.MM.NN` scheme unchanged.
- `scripts/conformance-check.sh` — **rewritten to introspect actual pytest
  test IDs via `pytest --collect-only --quiet`** instead of regexing raw
  file text against hardcoded patterns. This is the direct fix for the
  brittle-regex CI failure identified in the earlier project review
  (commit `0f37227` claimed to fix CI but the conformance gate still failed
  because test descriptions didn't match its exact expected phrasing) — the
  Python version does not re-import that bug.
- `.github/workflows/*.yml` (ci-core, develop-integration, feature-pr,
  hotfix, release, ci-autofix) — steps swapped from
  npm-install/tsc/jest to uv-sync/ruff/mypy/pytest. Same job names, same
  Gitflow trigger structure. The Gitflow-ceremony-weight question is
  explicitly out of scope for this port.

## Testing

- `testing/conformance/*.test.ts` → `tests/conformance/test_*.py`, same
  assertions, 1:1 translation.
- The 5 conformance tests currently marked `# TODO` in the TS suite (see
  §17 CLAUDE.md) are ported as `pytest.mark.skip(reason="TODO: ...")` —
  preserved as-is. Implementing real assertions for them is phase-3 work,
  not translation scope.
- `StubLLMClient`, `NullTelemetry`, `NullContext`, fixture factories all
  port directly as deterministic test doubles.

## Docs

- `CLAUDE.md` illustrative code blocks (§5 interface catalog, §8
  specialization examples, §10 Template Method walkthrough) translated from
  TS pseudocode to Python, since the concrete repo is now Python-primary.
  The "backend-agnostic, implementable in any typed language" philosophy in
  the prose is untouched — only code samples change language.
- `README.md` quick-start examples updated to Python imports/usage.
- `CONTRIBUTORS.md` contribution commands updated to `uv`/`ruff`/`mypy`/
  `pytest`; TS-specific code-standards bullet ("strict mode, no `any`")
  replaced with Python equivalents (`mypy --strict`, no untyped defs).

## Cutover

Single coherent change, sequenced as:

1. Add the full Python tree (`src/ooagent/`, `tests/`, `pyproject.toml`,
   rewritten scripts and workflows).
2. Verify: `uv run mypy --strict`, `uv run ruff check`, `uv run pytest` all
   green, matching or exceeding current TS test coverage.
3. Remove `*.ts` sources, `package.json`, `tsconfig.json`, `dist/`,
   `node_modules/` (gitignored, not tracked — deleted from the working tree
   only, no git action needed for it).
4. Update `.gitignore` (drop TS/node entries no longer relevant, add
   `.venv/`, `__pycache__/`, `*.egg-info/`).

## Out-of-scope confirmation

`packages/autogen-tools`, `packages/copilot-extension`, `packages/mcp-server`
are left untouched by this port. They remain TypeScript for now; each is a
separate future decision (documented here so it isn't mistaken for an
oversight).
