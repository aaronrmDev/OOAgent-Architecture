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
