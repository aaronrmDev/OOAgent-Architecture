# OOAgent as an MCP Server

OOAgent can run as a [Model Context Protocol](https://modelcontextprotocol.io)
(MCP) server — a host-agnostic plugin surface. Any MCP-compliant host
(Claude Code, Claude Desktop, and others as their MCP support matures)
can install it the same way, since MCP is one open protocol rather than
a per-host packaging format.

## What it exposes

- **Tool `respond`** — takes a `query` string, runs it through a real,
  fully-configured `OOAgent` instance (the complete FSM/`ConstraintEngine`/
  telemetry pipeline — CLAUDE.md §10's Template Method, nothing bypassed),
  and returns the resulting artifact's content as plain text.
- **Resource `contexts://list`** — read-only; lists the domain contexts
  currently registered with the running instance (just `NullContext` in
  this release — see "Known limitations" below).

## Configuration

The MCP server picks its own LLM backend via environment variables —
independently of whichever model the host itself runs, so "LLM-agnostic"
is a real, concrete property of the plugin, not just of the library:

| `OOAGENT_LLM_VENDOR` | Required API key env var |
|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `gemini` | `GEMINI_API_KEY` |
| `ollama` | none (local, no auth) |

Missing or invalid configuration fails fast with a clear message on
stderr before the server starts accepting connections — it never
silently falls back to a stub.

## Installing in Claude Code

```bash
claude mcp add ooagent \
  -e OOAGENT_LLM_VENDOR=anthropic \
  -e ANTHROPIC_API_KEY=sk-... \
  -- uv run --directory /path/to/OOAgent-Architecture ooagent-mcp
```

(Once published to PyPI, `uv run --directory /path/to/OOAgent-Architecture
ooagent-mcp` can be replaced with `uvx --from 'ooagent[mcp]' ooagent-mcp`
— no local checkout needed.)

## Known limitations

- Only `NullContext` is registered — a custom `IDomainContext` requires
  forking/extending `ooagent/mcp/config.py` today, not a runtime option.
- Registration and the MCP stdio handshake are confirmed working
  against a real Claude Code session (`claude mcp add` /
  `claude mcp list` show a genuine connection using the shipped
  `ooagent-mcp` entry point). A live `respond` tool call through a host
  has not yet been confirmed end-to-end — that needs a session restart
  (MCP servers added mid-session aren't picked up by the current
  session's own tool index) plus a real LLM credential or a reachable
  Ollama instance. Other MCP-compliant hosts should work identically
  (MCP is one protocol), but haven't been tried at all yet.
