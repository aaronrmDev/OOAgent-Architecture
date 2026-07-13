# OOAgent MCP Server — Design

## Purpose

OOAgent already advertises itself as LLM-agnostic (`ILLMClient` supports
Anthropic/OpenAI/Gemini/Ollama today) but is only consumable as a Python
library import — there is no way to *install and use* OOAgent inside an
AI coding-agent host (Claude Code, Claude Desktop, Antigravity, Cline,
etc.) without writing custom integration code per host. This feature adds
the missing half: a genuinely host-agnostic **plugin** surface, built on
the Model Context Protocol (MCP) — the open standard these hosts already
speak, rather than a bespoke per-host packaging format.

**Goal:** ship one new optional subpackage, `src/ooagent/mcp/`, exposing
a real, fully-configured `OOAgent` instance as an MCP server — installed
and verified end-to-end in Claude Code (this project's own dev
environment) as the first host. Because MCP is one protocol, any other
MCP-compliant host (Claude Desktop, Cline, and — pending its own MCP
compatibility — Antigravity) should work the same way without new code;
proving that is explicitly future work, not this pass's job.

## Scope

**In scope:**

1. `src/ooagent/mcp/server.py` — the MCP server itself: constructs one
   `OOAgent` instance from environment-variable configuration, exposes
   it via exactly two MCP primitives (below).
2. `src/ooagent/mcp/config.py` — env-var → `OOAgent` construction logic:
   reads `OOAGENT_LLM_VENDOR` (`anthropic`/`openai`/`gemini`/`ollama`)
   and that vendor's existing API-key env var (e.g.
   `ANTHROPIC_API_KEY`), constructs the matching `ILLMClient` adapter
   config, and builds an `OOAgent` with `NullContext` as the sole
   registered domain context for v1.
3. **Tool `respond`** — input: a query string. Runs the real
   `OOAgent.respond()` Template Method (FSM, `ConstraintEngine`,
   telemetry — the full pipeline, nothing bypassed) and returns the
   resulting `Artifact.content`. This is the single mechanism by which a
   host's LLM delegates a query to OOAgent — genuine "OOAgent as a
   plugin," not a bare pass-through to a raw LLM call.
4. **Resource `contexts`** — read-only: lists the names/scopes of every
   currently-registered `IDomainContext` (for v1, just `NullContext`),
   so a host's LLM can see what this OOAgent instance covers before
   deciding to call `respond`.
5. `pyproject.toml` — new `mcp` optional-dependency extra (mirrors the
   existing `otel` extra's pattern) pulling in the official `mcp` PyPI
   SDK (a brand-new dependency — verified absent from this repo and its
   `uv.lock` during brainstorming); new `[project.scripts]` section
   (this repo's first) registering `ooagent-mcp = "ooagent.mcp.server:main"`.
6. `docs/MCP.md` — install instructions (`claude mcp add`), the exact
   env vars, and what the two MCP primitives do — mirrors
   `docs/OBSERVABILITY.md`/`docs/EXTENDING.md`'s structure from the
   prior improvement backlog.
7. Real end-to-end verification: registering the built server in *this*
   Claude Code session via `claude mcp add` and actually invoking the
   `respond` tool for real, in addition to unit/integration tests.

**Out of scope:**

- **Other hosts** (Antigravity, Cline, Claude Desktop) — MCP is one
  protocol, so this should port without new code once Claude Code
  verification passes, but proving that against each host is separate,
  future work, not gated on this pass.
- **Fine-grained primitive exposure** (individual `ITool`s,
  `ConstraintEngine` checks, etc. as separate MCP tools) — considered
  and rejected during brainstorming: it would let a host's LLM bypass
  OOAgent's own FSM/validation pipeline, defeating the reason to install
  OOAgent specifically rather than just calling raw functions.
- **A Kimi (Moonshot AI) `ILLMClient` adapter** — raised during
  brainstorming and explicitly dropped from this feature: Kimi is a
  model API, not an agentic host: MCP servers plug into hosts, not
  models. If wanted later, it's a small, already-supported, unrelated
  extension point (`docs/EXTENDING.md`'s "LLM adapters" section, same
  shape as the existing `adapters/llm/ollama.py`).
- **Custom domain-context registration via the MCP server itself** —
  v1 always runs with `NullContext` only; registering a project-specific
  `IDomainContext` requires forking/extending the server code today
  (documented as a known limitation, not built as a runtime option).
- **Any change to `core/agent.py` or any other file under `src/ooagent/`
  outside the new `mcp/` subpackage** — this is purely additive; the
  `OOAgent` composition root and Template Method are used exactly as
  documented (CLAUDE.md §10), not modified.

## Architecture

```
Host (Claude Code, via stdio)
   │  MCP protocol (JSON-RPC over stdio)
   ▼
src/ooagent/mcp/server.py
   │  constructs once at startup
   ▼
src/ooagent/mcp/config.py ──builds──► OOAgent instance
                                         │  composes (unmodified, existing)
                                         ├── ILLMClient (whichever adapter env vars select)
                                         ├── ContextRegistry (NullContext only, v1)
                                         ├── ToolRegistry, PluginRegistry (empty, v1)
                                         └── ... (every other existing collaborator, untouched)
```

`server.py` owns the MCP-protocol concerns (tool/resource registration,
request/response marshaling); `config.py` owns environment-to-object
construction (Information Expert — mirrors how each existing
`adapters/llm/*.py` file owns its own `*Config` dataclass). Neither file
touches `core/`; both depend only on the existing public/advanced
surfaces already documented in `docs/PUBLIC_API.md`.

## Data Flow

1. Host process spawns `ooagent-mcp` (via `uvx` or a local install),
   connects over stdio per the MCP protocol.
2. `server.py` reads env vars once at startup (`config.py`), constructs
   one `OOAgent`, calls `initialize()`.
3. Host's LLM decides to read the `contexts` resource (optional) or call
   the `respond` tool with a query string.
4. `respond` tool handler calls `await agent.respond(Query(text=...))`,
   returns `artifact.content` as the tool result.
5. On host shutdown (or process exit), the server calls `agent.dispose()`.

## Error Handling

- Missing/invalid `OOAGENT_LLM_VENDOR` or missing API key at startup:
  fail fast with a clear stderr message before the MCP server starts
  accepting connections — do not silently fall back to a stub client.
- A `respond()` call that raises (should be rare — `OOAgent.respond()`
  already catches its own internal failures per CLAUDE.md §16 and
  returns a degraded `Artifact` rather than raising) — if something
  outside that contract still raises, the MCP tool handler surfaces it
  as an MCP tool-error result, not a silent empty response.

## Testing

- Unit/integration tests for `config.py`'s env-var → adapter-config
  construction (one test per vendor, plus the fail-fast-on-missing-key
  case), using this repo's existing `StubLLMClient`-style test-double
  pattern.
- Integration test(s) for the `respond` tool and `contexts` resource
  handlers using the MCP SDK's in-process test client against a real
  `OOAgent` backed by `StubLLMClient` (no live network calls, consistent
  with `docs/TESTING.md`'s existing no-network-calls discipline).
- Real end-to-end verification, done once implementation is complete:
  register the built server in this Claude Code session (`claude mcp
  add`) and invoke `respond` for real, confirming the full host round
  trip works, not just the protocol-level handlers in isolation.

## Out-of-Scope Confirmation

No file under `src/ooagent/core/`, `src/ooagent/adapters/`,
`src/ooagent/contexts/`, `src/ooagent/plugins/`, or
`src/ooagent/telemetry/` changes. `src/ooagent/workflow/` is untouched.
The only existing file modified is `pyproject.toml` (new optional extra
+ new `[project.scripts]` section); everything else is new, under
`src/ooagent/mcp/`, `docs/MCP.md`, and their paired tests.
