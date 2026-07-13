# OOAgent MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `src/ooagent/mcp/` — an MCP (Model Context Protocol) server exposing a real, fully-configured `OOAgent` instance to any MCP-compliant host, with a `respond` tool and a `contexts` resource, installable via `ooagent-mcp` and verified end-to-end in Claude Code.

**Architecture:** Two small, single-responsibility files. `config.py` reads environment variables and constructs an `OOAgent` (Information Expert on env → object construction, mirrors how each existing `adapters/llm/*.py` owns its own `*Config` dataclass). `server.py` owns MCP-protocol concerns only (tool/resource registration, the `main()` entry point) and depends on `config.py` for the actual agent — neither file touches `core/`.

**Tech Stack:** Python 3.11+, the official `mcp` PyPI SDK (`mcp.server.fastmcp.FastMCP` — the high-level decorator-based API), `anyio` (already a transitive dependency, confirmed present), this repo's existing `pytest`/`StubLLMClient` test stack.

## Global Constraints

- No file under `src/ooagent/core/`, `src/ooagent/adapters/`, `src/ooagent/contexts/`, `src/ooagent/plugins/`, `src/ooagent/telemetry/`, or `src/ooagent/workflow/` changes. The only existing files modified are `pyproject.toml` and the three CI workflow files' `uv sync` invocations (to add the new optional dependency to the sync command CI already runs).
- The `mcp` SDK's real API (verified by installing `mcp==1.28.1` and inspecting it directly — do not trust general training-data assumptions about its shape): `mcp.server.fastmcp.FastMCP(name: str)` is the server class; `@mcp_instance.tool()` decorates an async or sync function, using the function's name as the tool name and its docstring as the tool description; `@mcp_instance.resource(uri)` decorates a function similarly for a resource; `mcp_instance.run_stdio_async()` is the awaitable stdio-transport serve loop; `mcp_instance.run(transport="stdio")` is a sync convenience wrapper. For in-process testing: `mcp.shared.memory.create_connected_server_and_client_session(server)` is an async context manager yielding a connected `mcp.client.session.ClientSession`; `client.call_tool(name, {args})` returns a `CallToolResult` with `.content[0].text` (a `TextContent`) and `.isError`; `client.read_resource(uri)` (uri as a plain string is accepted) returns a `ReadResourceResult` with `.contents[0].text` (a `TextResourceContents`); `client.list_tools()`/`client.list_resources()` return `.tools`/`.resources` lists with `.name`/`.uri` attributes. All of this was confirmed against the installed package before this plan was written — do not deviate from these exact names/shapes without re-verifying against the installed `mcp` package yourself.
- Existing `ILLMClient` adapter configs (verified against the real source): `AnthropicConfig(api_key: str, model=None, max_tokens=None, base_url=None)` → `AnthropicLLMClient`; `OpenAIConfig(api_key: str, model=None, max_tokens=None, base_url=None)` → `OpenAILLMClient`; `GeminiConfig(api_key: str, model=None, max_tokens=None, base_url=None)` → `GeminiLLMClient`; `OllamaConfig(model=None, max_tokens=None, base_url=None)` (no `api_key` field — Ollama is local, no auth) → `OllamaLLMClient`. Import paths: `ooagent.adapters.llm.anthropic`, `.openai`, `.gemini`, `.ollama`.
- Env var names: `OOAGENT_LLM_VENDOR` (one of `anthropic`/`openai`/`gemini`/`ollama`), `ANTHROPIC_API_KEY` (existing convention, used verbatim in every `examples/*.py` file already), `OPENAI_API_KEY`, `GEMINI_API_KEY` (new conventions for this repo, following each vendor's own standard naming).
- `ContextRegistry` (`ooagent.core.registry`) has no public method to list registered contexts — only `.register(context)` and `.resolve(query)`, plus a private `._contexts` dict. Do not access `._contexts` directly (private attribute). Instead, `config.py`'s builder function returns the list of contexts it explicitly registered, alongside the `OOAgent`, so `server.py` never needs to introspect the registry.
- Each existing `ILLMClient` adapter (verified in `anthropic.py`) opens a fresh `async with httpx.AsyncClient() as client:` block per `complete()` call — no persistent, event-loop-bound resource is held across calls. Even so, `server.py`'s entry point constructs the agent, calls `initialize()`, serves, and calls `dispose()` all within one single `anyio.run(...)` call — one event loop for the whole process lifetime, avoiding any cross-event-loop hazard entirely.
- `StubLLMClient()` (`tests/stub_llm_client.py`, existing) returns `CompletionResponse(content="Default stub response.", ...)` when no `.add_script(...)` pattern matches — use this default behavior directly in integration tests rather than scripting a response.
- Full test suite, `ruff check .`, `ruff format --check`, and `mypy --strict` must stay clean after every task — this repo's CI treats all of these as blocking gates (per this session's own lint-gap lesson from an earlier sub-project, run these locally every task, not just `pytest`).

---

## File Structure

- Modify `pyproject.toml` — new `mcp` optional-dependency extra; later, a new `[project.scripts]` section (Task 3).
- Create `src/ooagent/mcp/__init__.py` — package marker + public re-exports (Task 2, extended in Task 3).
- Create `src/ooagent/mcp/config.py` — env-var → `(OOAgent, list[IDomainContext])` construction (Task 2).
- Create `src/ooagent/mcp/server.py` — the `FastMCP` server, `respond` tool, `contexts` resource, `main()` entry point (Task 3).
- Modify `.github/workflows/ci-core.yml`, `.github/workflows/develop-integration.yml`, `.github/workflows/sdd-gate.yml` — add `--extra mcp` to every `uv sync` invocation, so CI can import the new `tests/mcp/test_server.py` (Task 3).
- Create `docs/MCP.md` — install instructions, env vars, what the two primitives do (Task 4).
- Modify `README.md` — one new "Go Deeper" line (Task 4).
- Create `tests/mcp/__init__.py`, `tests/mcp/test_config.py` (Task 2), `tests/mcp/test_server.py` (Task 3).

---

### Task 1: `mcp` optional dependency

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: the `mcp` package importable when installed with the `mcp` extra — Tasks 3 depends on this (Task 2 does not: `config.py` only imports from `ooagent.*`, never from `mcp`).

- [ ] **Step 1: Add the `mcp` optional-dependency extra**

In `pyproject.toml`, find the `[project.optional-dependencies]` section:

```toml
[project.optional-dependencies]
otel = [
    "opentelemetry-api>=1.25",
    "opentelemetry-sdk>=1.25",
    "opentelemetry-exporter-otlp-proto-http>=1.25",
]
```

Add a new `mcp` extra immediately after `otel`:

```toml
[project.optional-dependencies]
otel = [
    "opentelemetry-api>=1.25",
    "opentelemetry-sdk>=1.25",
    "opentelemetry-exporter-otlp-proto-http>=1.25",
]
mcp = [
    "mcp>=1.28",
]
```

- [ ] **Step 2: Sync and verify**

Run: `uv sync --extra dev --extra otel --extra mcp`
Expected: succeeds, `uv.lock` is updated to include `mcp` and its transitive dependencies (`anyio`, `httpx-sse`, `pydantic`, `starlette`, `uvicorn`, etc. — confirmed transitive set from the real package).

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -c "import mcp; print(mcp.__version__ if hasattr(mcp, '__version__') else 'mcp import OK')"`
Expected: no `ModuleNotFoundError`.

- [ ] **Step 3: Confirm no regressions**

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS, same counts as before this task (adding a dependency doesn't change existing tests).

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add mcp as an optional dependency extra"
```

---

### Task 2: `src/ooagent/mcp/config.py` — env-var → `OOAgent` construction

**Files:**
- Create: `src/ooagent/mcp/__init__.py`
- Create: `src/ooagent/mcp/config.py`
- Test: `tests/mcp/__init__.py`
- Test: `tests/mcp/test_config.py`

**Interfaces:**
- Consumes: `AnthropicConfig`/`AnthropicLLMClient` (`ooagent.adapters.llm.anthropic`), `OpenAIConfig`/`OpenAILLMClient` (`ooagent.adapters.llm.openai`), `GeminiConfig`/`GeminiLLMClient` (`ooagent.adapters.llm.gemini`), `OllamaConfig`/`OllamaLLMClient` (`ooagent.adapters.llm.ollama`) — all existing, unmodified. `NullContext` (`ooagent.contexts.null_context`, existing). `OOAgent` (`ooagent.core.agent`, existing). `ContextRegistry` (`ooagent.core.registry`, existing). `IDomainContext`, `ILLMClient` (`ooagent.core.protocols`, existing).
- Produces: `class ConfigError(Exception)`, `def build_llm_client(env: Mapping[str, str] | None = None) -> ILLMClient`, `def build_agent(env: Mapping[str, str] | None = None) -> tuple[OOAgent, list[IDomainContext]]` — all in `ooagent.mcp.config`, re-exported from `ooagent.mcp`. Task 3's `server.py` imports `build_agent` and `ConfigError` from `.config`.

- [ ] **Step 1: Write the failing tests**

Create `tests/mcp/__init__.py` (empty file, package marker).

Create `tests/mcp/test_config.py`:

```python
"""tests/mcp/test_config.py — env-var to OOAgent construction."""

from __future__ import annotations

import pytest

from ooagent.adapters.llm.anthropic import AnthropicLLMClient
from ooagent.adapters.llm.gemini import GeminiLLMClient
from ooagent.adapters.llm.ollama import OllamaLLMClient
from ooagent.adapters.llm.openai import OpenAILLMClient
from ooagent.contexts.null_context import NullContext
from ooagent.core.agent import OOAgent
from ooagent.mcp.config import ConfigError, build_agent, build_llm_client


def test_build_llm_client_anthropic() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "anthropic", "ANTHROPIC_API_KEY": "key-1"})
    assert isinstance(client, AnthropicLLMClient)


def test_build_llm_client_openai() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "openai", "OPENAI_API_KEY": "key-2"})
    assert isinstance(client, OpenAILLMClient)


def test_build_llm_client_gemini() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "gemini", "GEMINI_API_KEY": "key-3"})
    assert isinstance(client, GeminiLLMClient)


def test_build_llm_client_ollama_needs_no_api_key() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "ollama"})
    assert isinstance(client, OllamaLLMClient)


def test_build_llm_client_missing_vendor_raises() -> None:
    with pytest.raises(ConfigError, match="OOAGENT_LLM_VENDOR"):
        build_llm_client({})


def test_build_llm_client_unsupported_vendor_raises() -> None:
    with pytest.raises(ConfigError, match="not supported"):
        build_llm_client({"OOAGENT_LLM_VENDOR": "not-a-real-vendor"})


def test_build_llm_client_anthropic_missing_key_raises() -> None:
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        build_llm_client({"OOAGENT_LLM_VENDOR": "anthropic"})


def test_build_agent_returns_agent_and_null_context() -> None:
    agent, contexts = build_agent({"OOAGENT_LLM_VENDOR": "ollama"})
    assert isinstance(agent, OOAgent)
    assert len(contexts) == 1
    assert isinstance(contexts[0], NullContext)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m pytest tests/mcp/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ooagent.mcp'` (the module doesn't exist yet).

- [ ] **Step 3: Create `src/ooagent/mcp/__init__.py`**

```python
"""ooagent.mcp — MCP (Model Context Protocol) server: OOAgent as a host-agnostic plugin."""

from ooagent.mcp.config import ConfigError, build_agent, build_llm_client

__all__ = [
    "ConfigError",
    "build_agent",
    "build_llm_client",
]
```

- [ ] **Step 4: Create `src/ooagent/mcp/config.py`**

```python
"""ooagent/mcp/config.py — environment-variable to OOAgent construction.

Information Expert on env -> object construction, mirroring how each
adapters/llm/*.py file owns its own *Config dataclass (CLAUDE.md §3).
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from ooagent.adapters.llm.anthropic import AnthropicConfig, AnthropicLLMClient
from ooagent.adapters.llm.gemini import GeminiConfig, GeminiLLMClient
from ooagent.adapters.llm.ollama import OllamaConfig, OllamaLLMClient
from ooagent.adapters.llm.openai import OpenAIConfig, OpenAILLMClient
from ooagent.contexts.null_context import NullContext
from ooagent.core.agent import OOAgent
from ooagent.core.protocols import IDomainContext, ILLMClient
from ooagent.core.registry import ContextRegistry

_VENDOR_ENV_VAR = "OOAGENT_LLM_VENDOR"
_SUPPORTED_VENDORS = ("anthropic", "openai", "gemini", "ollama")
_API_KEY_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


class ConfigError(Exception):
    """Raised when environment configuration is missing or invalid."""


def build_llm_client(env: Mapping[str, str] | None = None) -> ILLMClient:
    env = env if env is not None else os.environ
    vendor = env.get(_VENDOR_ENV_VAR)
    if not vendor:
        raise ConfigError(
            f"{_VENDOR_ENV_VAR} is not set. Set it to one of: "
            f"{', '.join(_SUPPORTED_VENDORS)}."
        )
    if vendor not in _SUPPORTED_VENDORS:
        raise ConfigError(
            f"{_VENDOR_ENV_VAR}={vendor!r} is not supported. Choose one of: "
            f"{', '.join(_SUPPORTED_VENDORS)}."
        )

    if vendor == "ollama":
        return OllamaLLMClient(OllamaConfig())

    api_key_var = _API_KEY_ENV_VARS[vendor]
    api_key = env.get(api_key_var)
    if not api_key:
        raise ConfigError(
            f"{api_key_var} is not set (required for {_VENDOR_ENV_VAR}={vendor})."
        )

    if vendor == "anthropic":
        return AnthropicLLMClient(AnthropicConfig(api_key=api_key))
    if vendor == "openai":
        return OpenAILLMClient(OpenAIConfig(api_key=api_key))
    return GeminiLLMClient(GeminiConfig(api_key=api_key))


def build_agent(env: Mapping[str, str] | None = None) -> tuple[OOAgent, list[IDomainContext]]:
    llm_client = build_llm_client(env)
    ctx_registry = ContextRegistry()
    null_context = NullContext()
    ctx_registry.register(null_context)
    agent = OOAgent(llm_client=llm_client, ctx_registry=ctx_registry)
    return agent, [null_context]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m pytest tests/mcp/test_config.py -v`
Expected: all 8 tests PASS.

- [ ] **Step 6: Run mypy and ruff**

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m mypy --strict`
Expected: `Success: no issues found in N source files` (N = prior count + 2 new files).

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 7: Run the full suite**

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS, prior count + 8 new tests.

- [ ] **Step 8: Commit**

```bash
git add src/ooagent/mcp/ tests/mcp/
git commit -m "feat(mcp): add env-var to OOAgent construction (config.py)"
```

---

### Task 3: `src/ooagent/mcp/server.py` — the MCP server

**Files:**
- Create: `src/ooagent/mcp/server.py`
- Modify: `src/ooagent/mcp/__init__.py`
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci-core.yml`, `.github/workflows/develop-integration.yml`, `.github/workflows/sdd-gate.yml`
- Test: `tests/mcp/test_server.py`

**Interfaces:**
- Consumes: `build_agent`, `ConfigError` (from Task 2's `ooagent.mcp.config`); `OOAgent.respond(query: Query) -> Artifact` and `OOAgent.initialize(config: AgentConfig) -> None` / `OOAgent.dispose() -> None` (existing, unmodified); `Query(text: str)`, `AgentConfig()` (existing, from `ooagent.core.protocols`); `mcp.server.fastmcp.FastMCP` (external SDK, verified shape in Global Constraints).
- Produces: `def build_server(agent: OOAgent, contexts: list[IDomainContext]) -> FastMCP`, `def main() -> None` — both in `ooagent.mcp.server`, `main` re-exported from `ooagent.mcp` and wired as the `ooagent-mcp` console script.

- [ ] **Step 1: Write the failing tests**

Create `tests/mcp/test_server.py`:

```python
"""tests/mcp/test_server.py — MCP server integration tests (in-process client)."""

from __future__ import annotations

from mcp.shared.memory import create_connected_server_and_client_session

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import AgentConfig
from ooagent.core.registry import ContextRegistry
from ooagent.contexts.null_context import NullContext
from ooagent.mcp.server import build_server
from tests.stub_llm_client import StubLLMClient


async def _build_test_agent() -> tuple[OOAgent, list]:
    ctx_registry = ContextRegistry()
    null_context = NullContext()
    ctx_registry.register(null_context)
    agent = OOAgent(llm_client=StubLLMClient(), ctx_registry=ctx_registry)
    await agent.initialize(AgentConfig())
    return agent, [null_context]


async def test_respond_tool_returns_agent_response() -> None:
    agent, contexts = await _build_test_agent()
    server = build_server(agent, contexts)

    async with create_connected_server_and_client_session(server) as client:
        await client.initialize()
        result = await client.call_tool("respond", {"query": "hello agent"})

        assert result.isError is False
        assert result.content[0].text == "Default stub response."

    await agent.dispose()


async def test_respond_tool_is_listed() -> None:
    agent, contexts = await _build_test_agent()
    server = build_server(agent, contexts)

    async with create_connected_server_and_client_session(server) as client:
        await client.initialize()
        tools = await client.list_tools()
        assert "respond" in [t.name for t in tools.tools]

    await agent.dispose()


async def test_contexts_resource_lists_null_context() -> None:
    agent, contexts = await _build_test_agent()
    server = build_server(agent, contexts)

    async with create_connected_server_and_client_session(server) as client:
        await client.initialize()
        resources = await client.list_resources()
        assert "contexts://list" in [str(r.uri) for r in resources.resources]

        result = await client.read_resource("contexts://list")
        assert "NullContext" in result.contents[0].text

    await agent.dispose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m pytest tests/mcp/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ooagent.mcp.server'`.

- [ ] **Step 3: Create `src/ooagent/mcp/server.py`**

```python
"""ooagent/mcp/server.py — OOAgent MCP server (FastMCP, stdio transport).

Owns MCP-protocol concerns only (tool/resource registration, the entry
point). Agent construction is config.py's job (Information Expert).
"""

from __future__ import annotations

import sys

import anyio
from mcp.server.fastmcp import FastMCP

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import AgentConfig, IDomainContext, Query

from .config import ConfigError, build_agent


def build_server(agent: OOAgent, contexts: list[IDomainContext]) -> FastMCP:
    mcp_server = FastMCP("ooagent")

    @mcp_server.tool()
    async def respond(query: str) -> str:
        """Send a query to the OOAgent instance and return its response."""
        artifact = await agent.respond(Query(text=query))
        return artifact.content

    @mcp_server.resource("contexts://list")
    def list_contexts() -> str:
        """List the domain contexts currently registered with this OOAgent instance."""
        lines = [f"{ctx.name} v{ctx.version}" for ctx in contexts]
        return "\n".join(lines) if lines else "(no domain contexts registered)"

    return mcp_server


async def _serve() -> None:
    try:
        agent, contexts = build_agent()
    except ConfigError as err:
        print(f"ooagent-mcp: {err}", file=sys.stderr)
        raise SystemExit(1) from err

    await agent.initialize(AgentConfig())
    mcp_server = build_server(agent, contexts)
    try:
        await mcp_server.run_stdio_async()
    finally:
        await agent.dispose()


def main() -> None:
    anyio.run(_serve)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Update `src/ooagent/mcp/__init__.py`**

Before:
```python
"""ooagent.mcp — MCP (Model Context Protocol) server: OOAgent as a host-agnostic plugin."""

from ooagent.mcp.config import ConfigError, build_agent, build_llm_client

__all__ = [
    "ConfigError",
    "build_agent",
    "build_llm_client",
]
```

After:
```python
"""ooagent.mcp — MCP (Model Context Protocol) server: OOAgent as a host-agnostic plugin."""

from ooagent.mcp.config import ConfigError, build_agent, build_llm_client
from ooagent.mcp.server import build_server, main

__all__ = [
    "ConfigError",
    "build_agent",
    "build_llm_client",
    "build_server",
    "main",
]
```

- [ ] **Step 5: Add the `[project.scripts]` entry point**

In `pyproject.toml`, add a new top-level section (this repo's first `[project.scripts]` section) — place it immediately after `[project.optional-dependencies]`'s closing and before `[build-system]`:

```toml
[project.scripts]
ooagent-mcp = "ooagent.mcp.server:main"
```

- [ ] **Step 6: Add `--extra mcp` to every CI `uv sync` invocation**

The new `tests/mcp/test_server.py` imports `mcp.shared.memory`, so CI must install the `mcp` extra or every job that runs `pytest` will fail on `ModuleNotFoundError`. Three files, every occurrence of `uv sync --extra dev --extra otel` becomes `uv sync --extra dev --extra otel --extra mcp`:

- `.github/workflows/ci-core.yml` — 4 occurrences (lines 32, 77, 100, 141 as of this plan being written; search-and-replace every occurrence, not just these line numbers, since they may have shifted).
- `.github/workflows/develop-integration.yml` — 5 occurrences.
- `.github/workflows/sdd-gate.yml` — 2 occurrences.

For each file, replace every instance of:
```yaml
        run: uv sync --extra dev --extra otel
```
or
```yaml
      - run: uv sync --extra dev --extra otel
```
with the same line, `--extra mcp` appended:
```yaml
        run: uv sync --extra dev --extra otel --extra mcp
```
or
```yaml
      - run: uv sync --extra dev --extra otel --extra mcp
```
(preserve each line's original indentation and leading `-` exactly — only append `--extra mcp` to the end of the existing command).

Verify every occurrence was caught:
Run: `grep -c "uv sync --extra dev --extra otel$" .github/workflows/ci-core.yml .github/workflows/develop-integration.yml .github/workflows/sdd-gate.yml`
Expected: `0` for every file (no occurrence left without `--extra mcp` appended — the `$` anchors to end-of-line, so any remaining match means a occurrence was missed).

- [ ] **Step 7: Run tests to verify they pass**

Run: `PYTHONPATH=src f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m pytest tests/mcp/test_server.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 8: Run mypy and ruff**

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m mypy --strict`
Expected: `Success: no issues found in N source files`.

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m ruff format --check`
Expected: all files already formatted (if not, run `ruff format` and re-check).

- [ ] **Step 9: Run the full suite**

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS, prior count + 3 new tests.

- [ ] **Step 10: Smoke-test the real entry point (no live LLM call needed)**

From the repo root, with `OOAGENT_LLM_VENDOR=ollama` set (no API key required, and `initialize()`/server startup never calls the LLM — only an actual `respond` tool invocation would, which this smoke test does not trigger):

```bash
OOAGENT_LLM_VENDOR=ollama timeout 3 f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m ooagent.mcp.server; echo "exit code: $?"
```

Expected: the process starts and blocks waiting for stdio input (an MCP client) — `timeout 3` kills it after 3 seconds. Expected exit code from the `timeout`-killed process is `124` (or `143`/similar signal-based code depending on platform — the key signal is the process did NOT exit immediately with a `ConfigError` message on stderr, which would indicate a startup failure). If you see `ooagent-mcp: ...` printed to stderr and an immediate exit, something is wrong — re-check Step 3's code against this step's env var.

- [ ] **Step 11: Commit**

```bash
git add src/ooagent/mcp/ tests/mcp/test_server.py pyproject.toml uv.lock .github/workflows/ci-core.yml .github/workflows/develop-integration.yml .github/workflows/sdd-gate.yml
git commit -m "feat(mcp): add the FastMCP server (respond tool, contexts resource, entry point)"
```

---

### Task 4: `docs/MCP.md`

**Files:**
- Create: `docs/MCP.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the finished `respond` tool / `contexts` resource / env vars from Tasks 2-3 (no code interfaces — docs-only task).
- Produces: nothing consumed by other tasks (final code-adjacent task in this plan; Task 5, the real end-to-end verification, is a controller-executed step described below, not a subagent-dispatched task).

- [ ] **Step 1: Verify every reference this doc will make**

Before writing, confirm (re-verify against the actual code from Tasks 2-3, since this repo has twice already caught docs drifting from real code this session — sub-project D's `OBSERVABILITY.md` and sub-project F's `SECURITY.md`):
- The tool is named `respond`, takes one `query: str` argument, returns the artifact's `content` as plain text.
- The resource URI is exactly `contexts://list`.
- The four supported `OOAGENT_LLM_VENDOR` values and their paired API-key env vars (`anthropic`→`ANTHROPIC_API_KEY`, `openai`→`OPENAI_API_KEY`, `gemini`→`GEMINI_API_KEY`, `ollama`→ none required).
- The console script name is `ooagent-mcp`.

- [ ] **Step 2: Create `docs/MCP.md`**

```markdown
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
- Verified against Claude Code as the first host. Other MCP-compliant
  hosts should work identically (MCP is one protocol), but that hasn't
  been verified against each one yet.
```

- [ ] **Step 3: Link from README**

Read the current `README.md`'s "Go Deeper" section first (its exact content may have shifted since this plan was written). Insert one new line:

```markdown
- [`docs/MCP.md`](docs/MCP.md) — run OOAgent as a host-agnostic MCP plugin (Claude Code, and any other MCP-compliant host)
```

immediately after the `docs/EXTENDING.md` line if present, otherwise immediately before the `CLAUDE.md` line — matching the insertion-position fallback rule already used by this session's prior docs-only sub-projects.

- [ ] **Step 4: Verify the full suite still passes**

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS, identical counts to Task 3's end state (docs-only change).

Run: `f:/Project/20260604-OOAgent-Architecture/.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add docs/MCP.md README.md
git commit -m "docs: add docs/MCP.md (install instructions, env vars, known limitations)"
```

---

## Task 5 (controller-executed, not subagent-dispatched): Real end-to-end verification

This step cannot be delegated to a subagent — it requires registering the
built server into *this actual* Claude Code session and invoking it for
real, which only the controlling session can do. After Tasks 1-4 are
implemented, reviewed, and the final whole-branch review passes:

1. From the finished worktree (or after merging to `develop`), run
   `claude mcp add ooagent-verify -e OOAGENT_LLM_VENDOR=ollama -- uv run
   --directory <worktree-or-repo-path> ooagent-mcp` (using `ollama` to
   avoid needing a real API key for this verification, assuming a local
   Ollama instance is reachable — if not, substitute a real
   `anthropic`/`ANTHROPIC_API_KEY` pair).
2. Confirm the server appears in `claude mcp list` and shows as
   connected.
3. Actually invoke the `respond` tool through the host (not just the
   in-process test client from Task 3) and confirm a real artifact comes
   back.
4. Remove the verification registration (`claude mcp remove
   ooagent-verify`) once confirmed — this was a verification step, not a
   permanent installation, unless the user wants to keep it installed.

## Self-Review

**Spec coverage:**
- `src/ooagent/mcp/server.py`/`config.py`, brand-new `mcp` dependency —
  Tasks 1-3. ✅
- `respond` tool + `contexts` resource — Task 3. ✅
- Env-var configuration, fail-fast on missing/invalid vendor or key —
  Task 2. ✅
- `pyproject.toml` `mcp` extra + `[project.scripts]` — Tasks 1 and 3. ✅
- `docs/MCP.md` — Task 4. ✅
- Unit tests (config.py, one per vendor + fail-fast cases) and
  integration tests (respond tool, contexts resource) using the MCP
  SDK's real in-process test client against a `StubLLMClient`-backed
  agent — Tasks 2 and 3. ✅
- Real end-to-end verification in this Claude Code session — Task 5
  (controller-executed). ✅
- Out-of-scope items (other hosts, fine-grained primitives, Kimi
  adapter, custom context registration, any `core/`/`adapters/`/
  `contexts/`/`plugins/`/`telemetry/`/`workflow/` change) — none touched
  by any task. ✅

**Placeholder scan:** no "TBD"/"TODO"/vague-instruction steps; every
code step has complete, verified-against-the-real-package content — the
`mcp` SDK's API shape was confirmed by installing it and inspecting it
directly during this plan's own research, not assumed.

**Type consistency:** `build_agent`'s return type
`tuple[OOAgent, list[IDomainContext]]` (Task 2) is consumed identically
by `build_server(agent: OOAgent, contexts: list[IDomainContext])`
(Task 3) and by `tests/mcp/test_server.py`'s local `_build_test_agent()`
helper, which mirrors the same shape without importing `build_agent`
directly (it needs a `StubLLMClient`, not a real vendor client) — no
signature drift between the two.
