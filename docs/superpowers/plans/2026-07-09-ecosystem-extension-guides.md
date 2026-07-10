# Ecosystem & Extension Guides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the one missing worked `CONTEXT.md` example (for the existing `UnitConversionContext`) and a single consolidated `docs/EXTENDING.md` that walks contributors through all four extension points (contexts, LLM adapters, tools, plugins), pointing at the best existing worked example for each rather than fabricating new ones.

**Architecture:** Purely additive documentation. No file under `src/ooagent/` changes except one clarifying cross-link line added to an existing docstring (see Global Constraints). Two new files (`examples/CONTEXT_EXAMPLE.md`, `docs/EXTENDING.md`), one new README line.

**Tech Stack:** Markdown only — no code, no new dependencies.

## Global Constraints

- No file under `src/ooagent/` is modified except `examples/domain_context_agent.py`'s module docstring, which gains exactly ONE new line (a cross-link to `examples/CONTEXT_EXAMPLE.md`) — no other change to that file. (The design spec's in-scope section calls for this one-line cross-link; its out-of-scope section's "no modifying `domain_context_agent.py`" bullet refers to rewriting/restructuring the example's logic, not this one-line addition — this note resolves that ambiguity for the implementer.)
- `core/protocols.py` is not touched — this pass documents the current compatibility contract (no automated version-range enforcement), it does not add enforcement.
- Every code/path reference written into either new doc must be verified against the real file at write time (exact line counts, exact class/function names, exact fixture names) — do not write a reference without opening the file first.
- Docs-only change: verification is (1) references checked against real files, (2) full test suite run at the end to confirm zero regressions (a docs-only change should show zero test diff).
- `examples/CONTEXT_EXAMPLE.md` follows CLAUDE.md §14's exact 10 required section headings, in order: Scope, Vocabulary (canonical terms), Problem Classes, Invariants, Anti-Patterns, Stack Defaults (if applicable), Artifact Preferences, System Prompt Extension, Extension Points, Known Limitations.
- Sample external packages are explicitly out of scope — `docs/EXTENDING.md` must say so, not omit it silently.

---

## File Structure

- Create `examples/CONTEXT_EXAMPLE.md` — worked CLAUDE.md §14 example for `UnitConversionContext` (Task 1).
- Modify `examples/domain_context_agent.py` — add one cross-link line to the module docstring (Task 1).
- Create `docs/EXTENDING.md` — consolidated four-extension-point guide (Task 2).
- Modify `README.md` — one new "Go Deeper" line (Task 2).

---

### Task 1: `examples/CONTEXT_EXAMPLE.md` — worked CONTEXT.md example

**Files:**
- Create: `examples/CONTEXT_EXAMPLE.md`
- Modify: `examples/domain_context_agent.py:1-26` (module docstring only)

**Interfaces:**
- Consumes: `UnitConversionContext` (`examples/domain_context_agent.py:51-115`, existing, unmodified) — this task only reads it to document it accurately.
- Produces: nothing consumed by Task 2 as a code interface; Task 2 links to this file by path.

- [ ] **Step 1: Verify the source content this doc will describe**

Read `examples/domain_context_agent.py` and confirm these exact facts (already verified while writing this plan, re-verify before writing since the implementer sees only this task):
- `vocabulary()` returns 4 terms: `meters` (SI unit of length), `feet` (imperial unit of length), `kilograms` (SI unit of mass), `pounds` (imperial unit of mass) — all `canonical=True`.
- `problem_classes()` returns one `ProblemClass(name="UnitConversion", description="Convert a quantity from one unit to another", solver="unit_converter")`.
- `solvers()` returns `{}` (empty dict) — deliberately, per the file's own docstring lines 10-12.
- `invariants()` returns one `Invariant(name="unit-tagged-result", condition="every converted quantity carries its target unit", severity="error", rationale="a bare number without a unit is not a valid conversion result")`.
- `pipeline()`, `anti_patterns()`, `required_inputs()` all return empty lists (`[]`).
- `artifact_preferences()` returns `ArtifactPolicy(preferred_formats=["text"], type_hints_required=False, comment_policy="none")`.
- `system_prompt_extension()` returns the exact string: `"UnitConversion v1.0 is active. Convert between the requested units and always state the target unit alongside the number."`
- `resolve_intent()` always returns `None`.

- [ ] **Step 2: Create `examples/CONTEXT_EXAMPLE.md`**

```markdown
# UnitConversion Context — v1.0 (Worked CONTEXT.md Example)

> This file is a worked example of the `CONTEXT.md` format required by
> CLAUDE.md §14 for every `IDomainContext` implementation. It documents
> `UnitConversionContext`, the domain context defined in
> `examples/domain_context_agent.py` (sub-project A's golden-path
> example). Real domain contexts under `contexts/<domain>/` should ship a
> `CONTEXT.md` in this same format, alongside their source — not as a
> standalone example file like this one.

## 1. Scope

Handles queries about converting a quantity from one measurement unit to
another (e.g., meters to feet). Declares one problem class,
`UnitConversion`, but does not implement a solver for it — `solvers()`
returns `{}` deliberately. This context exists to demonstrate *context
resolution and injection* (CLAUDE.md §9): a query mentioning "meters" or
"feet" resolves to `UnitConversionContext` instead of falling back to
`NullContext`. It does NOT demonstrate solver dispatch (CLAUDE.md §4's
Strategy pattern entry) — see Known Limitations below.

## 2. Vocabulary (canonical terms)

| Term | Definition | Canonical? |
|---|---|---|
| meters | SI unit of length | Yes |
| feet | imperial unit of length | Yes |
| kilograms | SI unit of mass | Yes |
| pounds | imperial unit of mass | Yes |

## 3. Problem Classes

| Name | Description | Required Inputs | Solver |
|---|---|---|---|
| UnitConversion | Convert a quantity from one unit to another | none declared (`required_inputs()` returns `[]`) | `unit_converter` (name only — no `ISolver` implementation is registered under it; a matched query falls through to the LLM/tool loop) |

## 4. Invariants

| Name | Condition | Severity | Rationale |
|---|---|---|---|
| unit-tagged-result | every converted quantity carries its target unit | error | a bare number without a unit is not a valid conversion result |

## 5. Anti-Patterns

None declared (`anti_patterns()` returns `[]`) — this minimal example
predates any anti-pattern discovered from production use of this context.

## 6. Stack Defaults (if applicable)

Not applicable — this context has no code-generation or stack-specific
behavior.

## 7. Artifact Preferences

`preferred_formats: ["text"]`, `type_hints_required: False`,
`comment_policy: "none"` — plain-text conversion answers, no code
artifact expected.

## 8. System Prompt Extension

The exact text injected into the LLM system prompt when this context is
active:

> "UnitConversion v1.0 is active. Convert between the requested units and
> always state the target unit alongside the number."

## 9. Extension Points

To turn this into a real, solver-backed domain context: implement an
`ISolver` that performs the actual unit-conversion arithmetic, register it
under the name `unit_converter` in `solvers()`, and add `required_inputs()`
entries for the source quantity, source unit, and target unit. To combine
this domain with another, compose rather than subclass (CLAUDE.md §8b's
`HybridContext` pattern) — merge vocabularies with `|` and concatenate
invariant lists.

## 10. Known Limitations

This context resolves but does not solve — every query correctly routed
here still falls through to the LLM/tool loop (`_llm_tool_loop`), because
`solvers()` is empty and `resolve_intent()` always returns `None`. It
exists purely to demonstrate `ContextRegistry.resolve()`'s vocabulary-
scoring algorithm (CLAUDE.md §9). A production unit-conversion context
should implement a real `ISolver` for deterministic, non-hallucinated
arithmetic rather than relying on the LLM to compute the conversion.
```

- [ ] **Step 3: Add the cross-link line to `examples/domain_context_agent.py`'s docstring**

The current docstring (lines 1-26) ends with:

```python
"""examples/domain_context_agent.py — Tier 3: a custom IDomainContext.

Defines UnitConversionContext, a small domain with real vocabulary
(units) and a system prompt extension. Demonstrates *context resolution
and injection* — ContextRegistry.resolve() scores a query against every
registered context's vocabulary, and a query mentioning "meters"/"feet"
resolves to UnitConversionContext instead of falling back to NullContext
(CLAUDE.md §9's resolution algorithm).

solvers() returns {} deliberately: this example is about context
resolution/injection, not solver dispatch, which is a separate, deeper
topic (see CLAUDE.md §4's Strategy pattern entry).

Run: uv run python -m examples.domain_context_agent

To use a real LLM backend instead of DemoLLMClient, replace the
llm_client below with, e.g.:

    import os
    from ooagent.adapters.llm.anthropic import AnthropicConfig, AnthropicLLMClient
    llm_client = AnthropicLLMClient(
        AnthropicConfig(api_key=os.environ["ANTHROPIC_API_KEY"], model="claude-opus-4-6"),
    )

Nothing else in this file changes.
"""
```

Add exactly one new paragraph immediately after the "solvers() returns {}
deliberately" paragraph (i.e., insert before the blank line that precedes
"Run: uv run python -m examples.domain_context_agent"):

```python
"""examples/domain_context_agent.py — Tier 3: a custom IDomainContext.

Defines UnitConversionContext, a small domain with real vocabulary
(units) and a system prompt extension. Demonstrates *context resolution
and injection* — ContextRegistry.resolve() scores a query against every
registered context's vocabulary, and a query mentioning "meters"/"feet"
resolves to UnitConversionContext instead of falling back to NullContext
(CLAUDE.md §9's resolution algorithm).

solvers() returns {} deliberately: this example is about context
resolution/injection, not solver dispatch, which is a separate, deeper
topic (see CLAUDE.md §4's Strategy pattern entry).

See CONTEXT_EXAMPLE.md alongside this file for a worked example of the
CLAUDE.md §14 CONTEXT.md format, filled out for UnitConversionContext.

Run: uv run python -m examples.domain_context_agent

To use a real LLM backend instead of DemoLLMClient, replace the
llm_client below with, e.g.:

    import os
    from ooagent.adapters.llm.anthropic import AnthropicConfig, AnthropicLLMClient
    llm_client = AnthropicLLMClient(
        AnthropicConfig(api_key=os.environ["ANTHROPIC_API_KEY"], model="claude-opus-4-6"),
    )

Nothing else in this file changes.
"""
```

Only that one paragraph is added. No other line in the file changes.

- [ ] **Step 4: Verify the example still runs**

Run: `uv run python -m examples.domain_context_agent`
Expected: unchanged output (identical to before this task — the docstring
change has no runtime effect):
```
resolved context: UnitConversion v1.0
system prompt extension: UnitConversion v1.0 is active. Convert between the requested units and always state the target unit alongside the number.
format:  text
content: 10 meters is approximately 32.8 feet.
```

- [ ] **Step 5: Run the full test suite**

From the repo root (or worktree root, with the `PYTHONPATH` override this
repo's shared-venv worktree setup requires — see Task 2's note below):
`f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS, identical pass/skip counts to before this task (this is a
docs-only change plus a one-line docstring addition — zero test diff
expected).

- [ ] **Step 6: Lint check**

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m ruff check examples/domain_context_agent.py`
Expected: `All checks passed!` (a docstring-only change cannot introduce a
ruff finding, but confirm anyway per this repo's lint-gap lesson from the
prior sub-project).

- [ ] **Step 7: Commit**

```bash
git add examples/CONTEXT_EXAMPLE.md examples/domain_context_agent.py
git commit -m "docs: add worked CONTEXT.md example for UnitConversionContext"
```

---

### Task 2: `docs/EXTENDING.md` and README link

**Files:**
- Create: `docs/EXTENDING.md`
- Modify: `README.md:54-62` (Go Deeper section — one new line)

**Interfaces:**
- Consumes: Task 1's `examples/CONTEXT_EXAMPLE.md` (linked by relative path, no code interface).
- Produces: nothing consumed by other tasks (final task in this plan).

- [ ] **Step 1: Verify every reference this doc will make**

Before writing, confirm each of these (all already verified while writing
this plan — re-confirm, since the implementer sees only this task):
- `src/ooagent/adapters/llm/ollama.py` is 134 lines, defines `OllamaConfig`
  and `OllamaLLMClient(ILLMClient)`, and its module docstring reads
  `"adapters/llm/ollama.py — ILLMClient -> Ollama local API
  (OpenAI-compatible)."`
- `tests/adapters/llm/conftest.py` defines the `mock_transport` fixture
  (type `MockTransportInstaller`, used as `mock_transport(handler)`) —
  documented in `docs/TESTING.md`.
- `src/ooagent/adapters/tools/base.py` defines `BaseTool` with a
  `_validate_args(self, args: dict[str, Any]) -> None` helper that checks
  `input_schema()`'s `required` fields, raising `ToolExecutionError` on a
  missing one.
- `src/ooagent/plugins/tool_kit/` contains three tools:
  `CalculatorTool` (`calculator_tool.py`, `name = "calculator"`),
  `DateTimeTool` (`datetime_tool.py`, `name = "datetime"`), and
  `HttpFetchTool` (`http_fetch_tool.py`, `name = "http_fetch"`, includes
  hostname validation — the most complete of the three).
- `src/ooagent/plugins/rate_limit/__init__.py` is 104 lines, defines
  `RateLimitOptions`, `RateLimitedTool(ITool)`, and
  `RateLimitPlugin(AbstractPlugin)` (`plugin_id = "ooagent.rate-limit"`),
  has no imports outside `ooagent.core.protocols` and
  `ooagent.plugins.base_plugin` plus stdlib (`math`, `time`, `dataclasses`,
  `typing`).
- `src/ooagent/core/protocols.py`'s `IPlugin` interface declares
  `plugin_id` and `version` properties (confirm via
  `grep -n "class IPlugin" -A 20 src/ooagent/core/protocols.py`) but no
  version-range/compatibility field — confirm this by grepping for
  `compatible|version_range|core_version|min_version` across
  `src/ooagent/core/protocols.py` and getting zero matches, exactly as
  verified during this plan's own research.

- [ ] **Step 2: Create `docs/EXTENDING.md`**

```markdown
# Extending OOAgent

OOAgent is closed for modification, open for extension (OCP — CLAUDE.md
§2). Every extension point follows the same 4-step pattern (CLAUDE.md
§22): implement the relevant interface, ship conformance tests, register
at agent startup, and never edit `core/`. This guide walks through each
of the four extension kinds with a pointer to the best existing worked
example for that kind. `CONTRIBUTORS.md`'s "What You Can Contribute"
section lists the required deliverables for each kind; this guide shows
what a finished one looks like.

## Domain contexts

Implement `IDomainContext` (CLAUDE.md §5's interface catalog, §8b's
specialization guide). The worked example is
`examples/domain_context_agent.py`'s `UnitConversionContext`, documented
in full per the CLAUDE.md §14 `CONTEXT.md` spec at
[`examples/CONTEXT_EXAMPLE.md`](../examples/CONTEXT_EXAMPLE.md) — read
that file alongside the source to see every required section filled out
for a real (if intentionally minimal) context. If your new context
overlaps an existing one, compose them (`HybridContext`, CLAUDE.md §8b)
rather than subclassing.

## LLM adapters

Implement `ILLMClient` (CLAUDE.md §5, §22). The simplest existing adapter
to copy is
[`src/ooagent/adapters/llm/ollama.py`](../src/ooagent/adapters/llm/ollama.py)
(134 lines — no API-key/auth handling, since Ollama runs locally). Test
it without live network calls using the `mock_transport` fixture in
`tests/adapters/llm/conftest.py` — see [`docs/TESTING.md`](TESTING.md)
for the full pattern (it monkeypatches `httpx.AsyncClient.__init__` so
adapters that construct their own client per call are still testable).

## Tools

Implement `ITool`, normally by extending `BaseTool`
(`src/ooagent/adapters/tools/base.py`), which provides `to_vendor_spec()`
for all four vendors and a `_validate_args()` helper that checks your
`input_schema()`'s `required` fields before `execute()` runs. Three
worked examples ship in `src/ooagent/plugins/tool_kit/`: `CalculatorTool`,
`DateTimeTool`, and `HttpFetchTool` — the last one is the most complete
example, since it also validates its input against a real external
concern (URL/hostname checks) rather than just types.

## Plugins

Implement `IPlugin`, normally by extending `AbstractPlugin`
(`src/ooagent/plugins/base_plugin.py`). The minimal worked template is
[`src/ooagent/plugins/rate_limit/`](../src/ooagent/plugins/rate_limit/__init__.py)
(104 lines, no external dependencies) — it wraps registered `ITool`
instances in a decorator (`RateLimitedTool`) and contributes them via
`contributes()`, without ever reaching into agent internals (CLAUDE.md
§21's plugin anti-pattern).

## Compatibility contract

Here is what actually happens today, not what CLAUDE.md §18 aspires to:
`ContextRegistry`, `ToolRegistry`, and `PluginRegistry` perform **no**
version-compatibility checking at registration time. `IPlugin` declares
`plugin_id` and `version` properties, but nothing in the codebase reads a
"compatible agent core version range" from a plugin — that is CLAUDE.md
§18's stated intent, not a built enforcement mechanism. The real contract
today is semver-by-convention on `core/protocols.py` (a breaking
interface change requires a major version bump, per §18), enforced by
human code review, not by any runtime check. If your context, tool, or
plugin only works against interfaces added after a certain version, say
so in your own `CONTEXT.md` or module docstring — there is no automated
field for it yet.

## What's not here yet

This repo does not currently ship a sample external package — a
separate, independently-versioned repository demonstrating OOAgent
consumed as a third-party pip dependency (as opposed to every example in
this repo, which imports `ooagent` from the same checkout). That is a
real gap, named here rather than silently glossed over: building and
maintaining a second repository is a larger commitment than this guide
covers.
```

- [ ] **Step 3: Link from README**

In `README.md`, modify the "Go Deeper" list (as it stands after
sub-project D's addition):

Before:
```markdown
## Go Deeper

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — composition root, design patterns, project structure, extension protocol
- [`docs/PUBLIC_API.md`](docs/PUBLIC_API.md) — what's core vs. advanced, and the stability contract
- [`docs/TESTING.md`](docs/TESTING.md) — how to test adapters without network calls, test doubles, coverage floor
- [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md) — event schema, failure taxonomy, wiring a telemetry backend, policy hooks and redaction
- [`CLAUDE.md`](CLAUDE.md) — the full architectural contract: invariants, FSM, failure modes, testing contracts
- [`CONTRIBUTORS.md`](CONTRIBUTORS.md) — how to contribute
```

After:
```markdown
## Go Deeper

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — composition root, design patterns, project structure, extension protocol
- [`docs/PUBLIC_API.md`](docs/PUBLIC_API.md) — what's core vs. advanced, and the stability contract
- [`docs/TESTING.md`](docs/TESTING.md) — how to test adapters without network calls, test doubles, coverage floor
- [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md) — event schema, failure taxonomy, wiring a telemetry backend, policy hooks and redaction
- [`docs/EXTENDING.md`](docs/EXTENDING.md) — worked examples for adding a domain context, LLM adapter, tool, or plugin
- [`CLAUDE.md`](CLAUDE.md) — the full architectural contract: invariants, FSM, failure modes, testing contracts
- [`CONTRIBUTORS.md`](CONTRIBUTORS.md) — how to contribute
```

If the "Go Deeper" section you actually find in `README.md` differs from
the "Before" block above (e.g. a different sub-project landed a different
line first), insert the new `docs/EXTENDING.md` line in the same
relative position (immediately after the `docs/OBSERVABILITY.md` line if
present, otherwise immediately after `docs/TESTING.md`) rather than
forcing an exact match — the requirement is one new line in the right
neighborhood, not a byte-identical block.

- [ ] **Step 4: Verify the full suite still passes**

Run (with the `PYTHONPATH` override if working from a worktree that
shares this repo's venv — see this plan's Global Constraints and
sub-project D's plan for why):
`f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS, 0 failures, identical counts to before this task (docs-only
change).

- [ ] **Step 5: Lint check**

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add docs/EXTENDING.md README.md
git commit -m "docs: add docs/EXTENDING.md (context/adapter/tool/plugin guides, compatibility contract)"
```

---

## Self-Review

**Spec coverage:**
- Worked `CONTEXT.md` example for `UnitConversionContext`, per CLAUDE.md §14's 10 sections — Task 1. ✅
- One-line cross-link from `domain_context_agent.py`'s docstring — Task 1, Step 3, with the spec-ambiguity resolved via this plan's Global Constraints note. ✅
- `docs/EXTENDING.md` covering all four extension kinds (contexts, adapters, tools, plugins) plus a compatibility-contract section and an explicit "what's not here yet" section — Task 2. ✅
- README link — Task 2, Step 3. ✅
- Out-of-scope items (sample external packages, `core/protocols.py` version-range field, new adapter/tool/plugin implementations, rewriting `domain_context_agent.py`'s logic) — none touched by either task; `docs/EXTENDING.md`'s "What's not here yet" section explicitly names the sample-external-package gap rather than omitting it. ✅

**Placeholder scan:** no "TBD"/"TODO"/vague-instruction steps; every step has complete, verified content.

**Type consistency:** not applicable (docs-only plan, no code interfaces beyond the one docstring paragraph, which is plain text).
