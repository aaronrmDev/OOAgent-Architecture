# Ecosystem & Extension Guides — Design

## Purpose

Sub-project E of the OOAgent improvement backlog (A: golden path, PR #8;
B: public API, PR #9; C: testing depth, PR #10; D: observability & safety,
PR #11). The original proposal asked for adapter/tool/plugin/context author
guides, compatibility contracts, and sample external packages.

Investigation found the same shape of gap as B, C, and D: the underlying
material is already mostly there — `CLAUDE.md` §8 (Inheritance &
Specialization Guide) and §14 (the `CONTEXT.md` specification) narratively
document every extension point, and `CONTRIBUTORS.md`'s "What You Can
Contribute" section already lists the required deliverables for each of the
four extension kinds. But two concrete things are missing:

1. **Zero worked `CONTEXT.md` examples exist in the repo.** §14 mandates
   every `IDomainContext` ship one, but the only context implementations in
   the codebase are `NullContext` (a Null Object, not a domain — no
   `CONTEXT.md` applies) and `examples/domain_context_agent.py`'s
   `UnitConversionContext` (a runnable script, not a `CONTEXT.md`). A
   contributor writing their first domain context has the spec's section
   headings but no filled-out example to pattern-match against.
2. **The four extension guides aren't tied together anywhere.** A
   contributor doesn't know, without already knowing the codebase, that
   `adapters/llm/ollama.py` (134 lines, no auth complexity) is the easiest
   adapter to copy, or that `plugins/rate_limit/` is a good minimal plugin
   template, or that `docs/TESTING.md`'s mock-transport pattern is how to
   test a new adapter without live network calls.

**Goal:** ship the one missing worked example (a `CONTEXT.md` for the
existing `UnitConversionContext`), and a single new `docs/EXTENDING.md` that
walks a contributor through all four extension points, pointing at the
best existing worked example for each rather than fabricating new ones
where good ones already exist.

## Scope

**In scope:**

1. `examples/CONTEXT_EXAMPLE.md` — a complete, filled-out `CONTEXT.md`
   (per CLAUDE.md §14's 10 required sections) for the existing
   `UnitConversionContext` (`examples/domain_context_agent.py`, unmodified —
   no changes to shipped example code). Cross-linked from that file's
   module docstring with one added line.
2. `docs/EXTENDING.md` — one consolidated guide covering all four
   extension kinds:
   - **Domain contexts** — points at `UnitConversionContext` +
     `examples/CONTEXT_EXAMPLE.md` as the worked pair, cross-references
     CLAUDE.md §14 and §8b (composition over inheritance for overlapping
     domains).
   - **LLM adapters** — points at `adapters/llm/ollama.py` as the simplest
     existing adapter to copy, and `docs/TESTING.md`'s `mock_transport`
     fixture pattern for testing without live network calls.
   - **Tools** — points at `plugins/tool_kit/`'s existing tools
     (`CalculatorTool`, `DatetimeTool`, `HttpFetchTool`) and `BaseTool`'s
     `_validate_args()` helper (CLAUDE.md §8c).
   - **Plugins** — points at `plugins/rate_limit/` as a minimal worked
     plugin template (104 lines, no external dependencies).
   - **Compatibility contract** — an honest statement of what's actually
     enforced today: `ContextRegistry`/`ToolRegistry`/`PluginRegistry` do
     no version compatibility checking at registration time; `IPlugin`
     declares `plugin_id`/`version` fields but nothing reads or enforces a
     "compatible agent core version range" despite CLAUDE.md §18's
     aspirational text — the actual contract today is semver-by-convention
     on `core/protocols.py`, enforced by human review, not by code. (This
     mirrors sub-project D's lesson: an honest "not yet enforced" beats a
     fabricated "this works automatically" claim.)
   - **What's out of scope for this doc** — see below.
3. One new line in README's "Go Deeper" list pointing at `docs/EXTENDING.md`.

**Out of scope:**

- **Sample external packages** (a separate pip-installable demo repo
  showing OOAgent consumed as a third-party dependency) — this needs its
  own repo, its own CI, and an ongoing maintenance commitment this pass
  doesn't have budget for. `docs/EXTENDING.md` will note this as a known
  gap rather than pretend one exists.
- **Adding a real `IPlugin` version-compatibility-range field to
  `core/protocols.py`** — this is a `core/` change to the semver-stable
  file (CLAUDE.md §18), a materially bigger and riskier change than a docs
  pass. Documenting the current honest state (not enforced) is this pass's
  job; building the enforcement is a separate future sub-project.
- **New adapter/tool/plugin implementations** — `adapters/llm/ollama.py`,
  `plugins/tool_kit/`, and `plugins/rate_limit/` are already good enough
  worked examples; this pass points at them rather than duplicating them.
- **Moving or modifying `examples/domain_context_agent.py`** — sub-project
  A already shipped and reviewed this file; `CONTEXT_EXAMPLE.md` is a new
  sibling file, not a rewrite.

## `docs/EXTENDING.md` structure

```markdown
# Extending OOAgent

## Before you start
[one-paragraph pointer to CLAUDE.md §22 Extension Protocol's 4-step
pattern shared by every extension kind: implement the interface, ship
conformance tests, register at startup, no edits to core/]

## Domain contexts
[UnitConversionContext + CONTEXT_EXAMPLE.md as the worked pair; link
CLAUDE.md §14 spec and §8b composition-over-inheritance guidance]

## LLM adapters
[ollama.py as the simplest worked example; docs/TESTING.md's
mock_transport pattern for testing]

## Tools
[plugins/tool_kit/'s three tools; BaseTool._validate_args() helper]

## Plugins
[plugins/rate_limit/ as the minimal worked template]

## Compatibility contract
[honest statement: semver-by-convention on core/protocols.py, no
automated version-range enforcement today, despite IPlugin declaring
plugin_id/version fields]

## What's not here yet
[sample external packages — explicitly named as a known gap, not silently
omitted]
```

## `examples/CONTEXT_EXAMPLE.md` structure

Follows CLAUDE.md §14's 10 required sections exactly, filled out for
`UnitConversionContext`'s actual behavior (vocabulary of 4 terms, one
`UnitConversion` problem class with no solver implementation — `solvers()`
returns `{}` deliberately per that file's own docstring — invariants,
empty pipeline/anti-patterns/required-inputs, `text`-only artifact
preferences, the exact `system_prompt_extension()` string, and `9. Extension
Points` / `10. Known Limitations` sections explaining this is a resolution
demo, not a solving demo, and that a real domain context would implement
`solvers()`).

## Testing

Docs-only change — no new test files. Verification is:
- `docs/EXTENDING.md`'s code/path references (`adapters/llm/ollama.py`,
  `plugins/rate_limit/`, `plugins/tool_kit/`, `BaseTool._validate_args()`,
  `docs/TESTING.md`'s fixture name) are checked against the real files at
  write time, not asserted by an automated test — the same verification
  discipline sub-project D's final review applied to `docs/OBSERVABILITY.md`.
- `examples/CONTEXT_EXAMPLE.md`'s claims about `UnitConversionContext`'s
  behavior (vocabulary terms, problem class, invariants, prompt extension
  text) are checked against the actual current file content, not assumed.
- Full test suite run at the end to confirm zero regressions (a docs-only
  change should show zero test diff).

## Out-of-scope confirmation

No file under `src/ooagent/` changes. `examples/domain_context_agent.py`
is read but not modified. `core/protocols.py` is not touched — the
compatibility-contract section documents the current state, it does not
add enforcement.

## Process note

Decided autonomously per the explicit "adecuate the best decisions ...
until finishing" AFK grant (reconfirmed with "Authorized" after sub-project
D's completion) — no interactive brainstorming checkpoint for this
sub-project, mirroring sub-project D's process.
