# Golden Path & Positioning — Design

## Purpose

The architecture is strong but the onboarding path isn't: `README.md`
currently leads with a composition-root diagram and a project-structure
tree before saying who the framework is for or what problem it solves,
and its "Quick Start" snippets are illustrative fragments (`...`,
"implement the remaining 10 methods …") rather than complete, runnable
examples. This is sub-project **A** of a 6-part improvement backlog
(A–F) scoped during brainstorming; A is first because B–F all benefit
from a working golden path existing to reference.

**Goal:** a developer can go from `git clone` to a working, validated
agent response in under 5 minutes, with zero API keys, and see exactly
what "testable," "provider-portable," and "observable" mean in practice
— not just read that they're true.

## Scope

**In scope:**

1. `README.md` rewrite: positioning (what/who/not) → condensed golden
   path → links out, replacing the current architecture-diagram-first
   structure.
2. New `docs/ARCHITECTURE.md`: receives the current README's
   composition diagram, project-structure tree, pattern catalog, and
   SOLID table — moved near-verbatim, not rewritten.
3. Four new runnable examples under `examples/`, each a single
   self-contained file, each printing its output:
   - `examples/minimal_agent.py`
   - `examples/tool_enabled_agent.py`
   - `examples/domain_context_agent.py`
   - `examples/telemetry_enabled_agent.py`
4. `tests/examples/test_examples.py` — one test per example, running it
   end-to-end (not just checking the file exists) and asserting on its
   output.

**Out of scope** (deferred to sub-projects B–F, see the brainstorming
session's decomposition table):

- Public API/stability documentation, config-object redesign (B)
- Behavior-matrix / property-based / failure-mode test suites (C)
- Structured event schema, tracing, policy hooks, redaction (D)
- Extension-author guides, compatibility contracts, sample external
  packages (E)
- CONTRIBUTING/ADRs, roadmap, changelog, security policy, docs site (F)

## Positioning content (goes at the top of the rewritten README)

```
**What it is:** a composition framework for building type-safe,
provider-portable AI agents with validation, testability, and
observability enforced by construction — not layered on after.

**Who it's for, first:** app teams building production agents who want
architectural discipline, provider portability, and testability without
hand-rolling it. (Framework authors extending OOAgent and researchers
prototyping agent architectures are also served, but production app
teams are who the golden path below is written for.)

**What it's explicitly not:**
- not a chat UI
- not a low-code/visual workflow builder
- not an autonomous, unsupervised agent runner — the FSM is turn-based
  and gate-enforced (§10-12 CLAUDE.md), not a free-running loop
- not a prompt-template library
```

## The four examples

Each example is a complete, directly-runnable Python file
(`python examples/<name>.py`, no CLI framework, no argparse) using
`StubLLMClient` so it needs zero API keys and zero network access —
each file's docstring shows the one-line swap to a real
`AnthropicLLMClient`/`OpenAILLMClient` for production use. All four
construct their own `ContextRegistry`/`ToolRegistry` instances
explicitly (dependency injection) rather than relying on
`ContextRegistry.get_instance()`'s process-wide singleton — this keeps
each example self-contained and avoids hidden global state leaking
between examples when the test suite runs them in one process.

1. **`minimal_agent.py`** — `OOAgent(llm_client=StubLLMClient())`,
   `initialize()`, one `Query`, one `Artifact` back, `dispose()`. No
   context or tool registration — `ContextRegistry` falls back to
   `NullContext` automatically when nothing is registered (§9
   CLAUDE.md's resolution algorithm). Prints the artifact's `content`
   and `format`.

2. **`tool_enabled_agent.py`** — adds a `ToolRegistry` with the
   existing `CalculatorTool` (`plugins/tool_kit/calculator_tool.py`,
   already ships in the framework — no new tool code needed) registered
   and injected via `OOAgent(tool_registry=...)`.

3. **`domain_context_agent.py`** — a new, small `IDomainContext`
   (`UnitConversionContext`) defined inline in the example file (not
   shipped as part of `src/ooagent/`), with a real `vocabulary()`
   (units: meters, feet, kilograms, pounds), a `ProblemClass`, and a
   `system_prompt_extension()`. `solvers()` returns `{}` — this example
   demonstrates *context resolution and injection* (a query mentioning
   "meters" and "feet" scores above threshold and `ContextRegistry`
   resolves to `UnitConversionContext` instead of `NullContext`), not
   solver-dispatch internals, which is a separate, deeper topic. A
   comment says so explicitly, so nobody mistakes the omission for a
   missing feature.

4. **`telemetry_enabled_agent.py`** — wires the existing
   `ConsoleTelemetry` (`telemetry/console.py`) via
   `OOAgent(telemetry=...)`, so running it prints span/event lines
   alongside the artifact — the observability story made visible, not
   just asserted.

Every example ends with a `print()` block showing the actual artifact
content and format, so "expected output" is something a reader sees by
running the file, not something they have to imagine.

## Testing

`tests/examples/test_examples.py` imports each example's `main()`
coroutine directly (each example wraps its body in
`async def main() -> None:` + `asyncio.run(main())` under
`if __name__ == "__main__":`, so tests import and `await main()`
without spawning a subprocess) and asserts:
- it completes without raising
- for `tool_enabled_agent`/`domain_context_agent`, the relevant
  registry/context was actually exercised (e.g. the resolved context's
  `name` matches `"UnitConversion"`, not `"NullContext"`)
- for `telemetry_enabled_agent`, at least one telemetry call fired
  (capture via `capsys` and check for the `[Telemetry]` prefix)

This is new coverage, additive under `tests/` — no changes to
`ci-core.yml` are needed since it already runs
`PYTHONPATH=src uv run pytest tests/ -v` (or the conformance subset);
a repo-wide `uv run pytest` picks up `tests/examples/` automatically.

## README restructure (new outline)

```
# OOAgent — Object-Oriented AI Agent Framework
[badges]
[one-line tagline]

## What OOAgent Is
## Who It's For
## What It's Not

## Golden Path
  (install → run examples/minimal_agent.py → show its output →
   link to examples/ for the other 3 tiers)

## Go Deeper
  - docs/ARCHITECTURE.md — composition root, patterns, project structure
  - CLAUDE.md — the full architectural contract
  - CONTRIBUTORS.md

## Supported LLM Backends
  (kept — short table, unchanged content)

## Testing
  (kept — short, unchanged content)

## License
  (kept, unchanged)
```

Everything currently under "Architecture at a Glance," "Project
Structure," "Design Patterns Applied," and "SOLID Compliance" moves to
`docs/ARCHITECTURE.md` verbatim. "Extending OOAgent" and "Output
Discipline" move there too, since they're architecture-depth content,
not golden-path content — a first-time reader doesn't need the plugin
contribution protocol to get their first response back.

## Out-of-scope confirmation

No source code under `src/ooagent/core/`, `adapters/`, `contexts/`,
`plugins/`, or `telemetry/` changes — this sub-project only adds new
files (`examples/`, `tests/examples/`, `docs/ARCHITECTURE.md`) and
restructures `README.md`. `CLAUDE.md` is read (for cross-references)
but not modified.
