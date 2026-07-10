# Public API & Stability Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** make `from ooagent import OOAgent` (and 16 other curated core-primitive names) work, backed by an identity-asserting test, and document the core-vs-advanced API split so users know which tier they need.

**Architecture:** `src/ooagent/__init__.py` gains a curated re-export (no wildcard) of exactly 17 names — everything the sub-project A golden-path examples already import directly, plus the exception hierarchy. `tests/test_public_api.py` asserts each top-level name `is` (not just `==`) its canonical submodule counterpart, so a future refactor that silently re-defines rather than re-imports a name fails loudly. `docs/PUBLIC_API.md` documents the split and links to CLAUDE.md §18's existing versioning strategy rather than restating it.

**Tech Stack:** Python 3.11, existing `ooagent` package — no new runtime dependencies.

## Global Constraints

- Full design: `docs/superpowers/specs/2026-07-06-public-api-stability-design.md`.
- The top-level export list is exactly these 17 names, no more, no fewer: `OOAgent`, `AgentConfig`, `Query`, `Artifact`, `ILLMClient`, `IDomainContext`, `ITool`, `IPlugin`, `ContextRegistry`, `ToolRegistry`, `OOAgentError`, `ConstraintViolationError`, `FSMViolationError`, `LifecycleError`, `ToolExecutionError`, `TokenLimitError`, `ScopeExitError`. (The design doc's testing section said "14 total" — that undercounted; the actual list above has 17 names. This plan uses the correct count.)
- No changes to `src/ooagent/core/`, `adapters/`, `contexts/`, `plugins/`, `telemetry/`, or `workflow/`'s existing `__all__` lists or behavior — only `src/ooagent/__init__.py` gains new content (it's currently a bare one-line docstring).
- No changes to `AgentConfig`'s fields or `pyproject.toml`'s version scheme (both explicitly out of scope per the design doc).
- Every new import uses explicit names (`from X import A, B, C`), never `import *` — the whole point is a curated, non-wildcard top-level surface.
- Run `PYTHONPATH=src uv run pytest tests/ -q` after every task to confirm the full suite (old + new) stays green.

---

### Task 1: `src/ooagent/__init__.py` curated barrel export + identity test

**Files:**
- Modify: `src/ooagent/__init__.py` (currently a bare docstring — replace entirely)
- Create: `tests/test_public_api.py`

**Interfaces:**
- Consumes: `OOAgent` (`ooagent.core.agent`); `AgentConfig, Artifact, ConstraintViolationError, FSMViolationError, IDomainContext, ILLMClient, IPlugin, ITool, LifecycleError, OOAgentError, Query, ScopeExitError, TokenLimitError, ToolExecutionError` (`ooagent.core.protocols`); `ContextRegistry, ToolRegistry` (`ooagent.core.registry`) — all pre-existing, unchanged.
- Produces: `ooagent.__all__` (the 17-name list) — consumed by Task 2's documentation, which must describe this exact list.

- [ ] **Step 1: Write the failing test**

Create `tests/test_public_api.py`:

```python
"""tests/test_public_api.py — the top-level ooagent import surface (docs/PUBLIC_API.md)."""

from __future__ import annotations

import ooagent
from ooagent.core.agent import OOAgent as _OOAgent
from ooagent.core.protocols import AgentConfig as _AgentConfig
from ooagent.core.protocols import Artifact as _Artifact
from ooagent.core.protocols import ConstraintViolationError as _ConstraintViolationError
from ooagent.core.protocols import FSMViolationError as _FSMViolationError
from ooagent.core.protocols import IDomainContext as _IDomainContext
from ooagent.core.protocols import ILLMClient as _ILLMClient
from ooagent.core.protocols import IPlugin as _IPlugin
from ooagent.core.protocols import ITool as _ITool
from ooagent.core.protocols import LifecycleError as _LifecycleError
from ooagent.core.protocols import OOAgentError as _OOAgentError
from ooagent.core.protocols import Query as _Query
from ooagent.core.protocols import ScopeExitError as _ScopeExitError
from ooagent.core.protocols import TokenLimitError as _TokenLimitError
from ooagent.core.protocols import ToolExecutionError as _ToolExecutionError
from ooagent.core.registry import ContextRegistry as _ContextRegistry
from ooagent.core.registry import ToolRegistry as _ToolRegistry


def test_ooagent_is_the_same_object_as_core_agent_ooagent() -> None:
    assert ooagent.OOAgent is _OOAgent


def test_agent_config_is_the_same_object_as_core_protocols_agent_config() -> None:
    assert ooagent.AgentConfig is _AgentConfig


def test_query_is_the_same_object_as_core_protocols_query() -> None:
    assert ooagent.Query is _Query


def test_artifact_is_the_same_object_as_core_protocols_artifact() -> None:
    assert ooagent.Artifact is _Artifact


def test_illmclient_is_the_same_object_as_core_protocols_illmclient() -> None:
    assert ooagent.ILLMClient is _ILLMClient


def test_idomaincontext_is_the_same_object_as_core_protocols_idomaincontext() -> None:
    assert ooagent.IDomainContext is _IDomainContext


def test_itool_is_the_same_object_as_core_protocols_itool() -> None:
    assert ooagent.ITool is _ITool


def test_iplugin_is_the_same_object_as_core_protocols_iplugin() -> None:
    assert ooagent.IPlugin is _IPlugin


def test_context_registry_is_the_same_object_as_core_registry_context_registry() -> None:
    assert ooagent.ContextRegistry is _ContextRegistry


def test_tool_registry_is_the_same_object_as_core_registry_tool_registry() -> None:
    assert ooagent.ToolRegistry is _ToolRegistry


def test_ooagent_error_is_the_same_object_as_core_protocols_ooagent_error() -> None:
    assert ooagent.OOAgentError is _OOAgentError


def test_constraint_violation_error_is_the_same_object_as_core_protocols_version() -> None:
    assert ooagent.ConstraintViolationError is _ConstraintViolationError


def test_fsm_violation_error_is_the_same_object_as_core_protocols_version() -> None:
    assert ooagent.FSMViolationError is _FSMViolationError


def test_lifecycle_error_is_the_same_object_as_core_protocols_version() -> None:
    assert ooagent.LifecycleError is _LifecycleError


def test_tool_execution_error_is_the_same_object_as_core_protocols_version() -> None:
    assert ooagent.ToolExecutionError is _ToolExecutionError


def test_token_limit_error_is_the_same_object_as_core_protocols_version() -> None:
    assert ooagent.TokenLimitError is _TokenLimitError


def test_scope_exit_error_is_the_same_object_as_core_protocols_version() -> None:
    assert ooagent.ScopeExitError is _ScopeExitError


def test_all_exports_exactly_match_the_dunder_all_list() -> None:
    expected = {
        "OOAgent",
        "AgentConfig",
        "Query",
        "Artifact",
        "ILLMClient",
        "IDomainContext",
        "ITool",
        "IPlugin",
        "ContextRegistry",
        "ToolRegistry",
        "OOAgentError",
        "ConstraintViolationError",
        "FSMViolationError",
        "LifecycleError",
        "ToolExecutionError",
        "TokenLimitError",
        "ScopeExitError",
    }
    assert set(ooagent.__all__) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src uv run pytest tests/test_public_api.py -v`
Expected: FAIL — every test errors with `AttributeError: module 'ooagent' has no attribute 'OOAgent'` (or similar), since `src/ooagent/__init__.py` currently exports nothing.

- [ ] **Step 3: Write the implementation**

Replace the entire contents of `src/ooagent/__init__.py` with:

```python
"""ooagent — Object-Oriented AI Agent Framework (backend-agnostic, domain-agnostic).

Core primitives — the surface most app teams need:

    from ooagent import OOAgent, AgentConfig, Query, Artifact

Extension-point interfaces and the two registries the golden-path
examples (examples/*.py) already touch directly:

    from ooagent import ILLMClient, IDomainContext, ITool, IPlugin
    from ooagent import ContextRegistry, ToolRegistry

The exception hierarchy, catchable without deep imports:

    from ooagent import OOAgentError, ConstraintViolationError, FSMViolationError
    from ooagent import LifecycleError, ToolExecutionError, TokenLimitError, ScopeExitError

Everything else (ArtifactFactory, ConstraintEngine, LifecycleManager,
MultiAgentOrchestrator, the advanced-only ABCs, IDeliveryWorkflow, ...) is
the "advanced" tier — reachable via `ooagent.core`, `ooagent.adapters`,
`ooagent.workflow`, etc. See docs/PUBLIC_API.md for the full split and the
stability contract (CLAUDE.md §18).
"""

from __future__ import annotations

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import (
    AgentConfig,
    Artifact,
    ConstraintViolationError,
    FSMViolationError,
    IDomainContext,
    ILLMClient,
    IPlugin,
    ITool,
    LifecycleError,
    OOAgentError,
    Query,
    ScopeExitError,
    TokenLimitError,
    ToolExecutionError,
)
from ooagent.core.registry import ContextRegistry, ToolRegistry

__all__ = [
    "OOAgent",
    "AgentConfig",
    "Query",
    "Artifact",
    "ILLMClient",
    "IDomainContext",
    "ITool",
    "IPlugin",
    "ContextRegistry",
    "ToolRegistry",
    "OOAgentError",
    "ConstraintViolationError",
    "FSMViolationError",
    "LifecycleError",
    "ToolExecutionError",
    "TokenLimitError",
    "ScopeExitError",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/test_public_api.py -v`
Expected: PASS (18 tests — 17 identity assertions + 1 completeness check)

- [ ] **Step 5: Confirm the existing golden-path examples still work unchanged**

Run: `uv run python -m examples.minimal_agent`
Expected: unchanged output (`format:  text` / `content: Hello! I'm a validated OOAgent response.`) — this task only adds a new top-level import path, it does not remove or change `ooagent.core.agent.OOAgent` or any other existing import path the examples already use.

- [ ] **Step 6: Run the full suite and lint**

Run: `PYTHONPATH=src uv run pytest tests/ -q`
Expected: all tests pass (old + 18 new)

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check`
Expected: mypy clean, ruff clean

- [ ] **Step 7: Commit**

```bash
git add src/ooagent/__init__.py tests/test_public_api.py
git commit -m "feat(api): add curated top-level ooagent barrel export"
```

---

### Task 2: `docs/PUBLIC_API.md` + README link

**Files:**
- Create: `docs/PUBLIC_API.md`
- Modify: `README.md` (append one line to the existing "Go Deeper" list)

**Interfaces:**
- Consumes: the 17-name list from Task 1 (documented as a table here).
- Produces: nothing consumed by other tasks — final task.

- [ ] **Step 1: Create `docs/PUBLIC_API.md`**

Create `docs/PUBLIC_API.md`:

```markdown
# Public API & Stability

## Core primitives (`from ooagent import ...`)

| Name | What it's for |
|---|---|
| `OOAgent` | The composition root — construct one per agent instance. |
| `AgentConfig` | Turn-level configuration: retries, timeouts, circuit-breaker threshold. |
| `Query` | The input to `OOAgent.respond()`. |
| `Artifact` | The validated output of `OOAgent.respond()`. |
| `ILLMClient` | Implement this to add a new LLM backend. |
| `IDomainContext` | Implement this to add a new domain (see `examples/domain_context_agent.py`). |
| `ITool` | Implement this (or extend `BaseTool`) to add a new tool. |
| `IPlugin` | Implement this to add a new plugin. |
| `ContextRegistry` | Holds registered `IDomainContext` instances; construct your own rather than relying on the process-wide singleton when you need isolation (see `examples/domain_context_agent.py`). |
| `ToolRegistry` | Holds registered `ITool` instances (see `examples/tool_enabled_agent.py`). |
| `OOAgentError` | Base of the exception hierarchy below. |
| `ConstraintViolationError` | Raised when `ConstraintEngine.assert_all()` fails. |
| `FSMViolationError` | Raised on an illegal FSM transition — always a programming error. |
| `LifecycleError` | Raised when calling `respond()`/`dispose()` outside the correct lifecycle phase. |
| `ToolExecutionError` | Raised by a tool's `execute()` on failure. |
| `TokenLimitError` | Raised when a request exceeds the LLM client's `max_tokens`. |
| `ScopeExitError` | Raised when a query falls outside every registered context's scope. |

## Advanced surface (`ooagent.core`, `ooagent.adapters`, `ooagent.workflow`, ...)

Everything not listed above — `ArtifactFactory`, `ConstraintEngine`,
`ResponsePipeline`, `LifecycleManager`, `MultiAgentOrchestrator`,
`SignalBus`, `ProvenanceTracker`, `ResponseDecorator`, `SessionState`,
`CircuitBreaker`, `PluginRegistry`, the advanced-only ABCs (`ISolver`,
`ILifecycle`, `ISessionState`, `ITelemetryProvider`, `IArtifactFactory`,
`IOrchestrator`, `IContextHost`, `IConversationalObject`, `IToolUser`,
`IObservable`, `IVisitor`, `IArtifactNode`, `IPrototypable`), every LLM
adapter (`AnthropicLLMClient`, `OpenAILLMClient`, ...), every built-in
plugin, and `IDeliveryWorkflow`/`SpecDrivenWorkflow` (a peer layer per
[CLAUDE.md §24](../CLAUDE.md), not core) — is reachable via
`ooagent.core`, `ooagent.adapters.*`, `ooagent.contexts`,
`ooagent.plugins.*`, `ooagent.telemetry`, or `ooagent.workflow`, exactly
as [`docs/ARCHITECTURE.md`](ARCHITECTURE.md)'s project-structure section
describes.

## Stability contract

Core primitives follow the same semver-stable rule
[CLAUDE.md §18](../CLAUDE.md) already states for `core/protocols.py`:
a breaking change to any name in the core-primitives table requires a
major version bump. Advanced-tier names may move between modules across
minor versions without a deprecation cycle, since they're
implementation-adjacent rather than the primary integration surface.

## Deciding which tier you need

- **Building an app on OOAgent** → core primitives are almost always
  enough. Start with [the golden path](../README.md#golden-path).
- **Extending the framework** (new adapter/tool/plugin/context) → you'll
  also need the submodule imports documented in
  [CLAUDE.md §22](../CLAUDE.md)'s extension protocol.
```

- [ ] **Step 2: Add the README link**

In `README.md`, find this exact text:

```
## Go Deeper

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — composition root, design patterns, project structure, extension protocol
- [`CLAUDE.md`](CLAUDE.md) — the full architectural contract: invariants, FSM, failure modes, testing contracts
- [`CONTRIBUTORS.md`](CONTRIBUTORS.md) — how to contribute
```

Replace it with:

```
## Go Deeper

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — composition root, design patterns, project structure, extension protocol
- [`docs/PUBLIC_API.md`](docs/PUBLIC_API.md) — what's core vs. advanced, and the stability contract
- [`CLAUDE.md`](CLAUDE.md) — the full architectural contract: invariants, FSM, failure modes, testing contracts
- [`CONTRIBUTORS.md`](CONTRIBUTORS.md) — how to contribute
```

- [ ] **Step 3: Confirm links resolve**

Run: `test -f docs/ARCHITECTURE.md && test -f CLAUDE.md && test -f docs/PUBLIC_API.md && echo "all targets exist"`
Expected: `all targets exist`

- [ ] **Step 4: Run the full verification suite**

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check && PYTHONPATH=src uv run pytest tests/ -q`
Expected: all pass — 0 mypy errors, 0 ruff findings, full test suite green (old + 18 new from Task 1)

- [ ] **Step 5: Commit**

```bash
git add docs/PUBLIC_API.md README.md
git commit -m "docs: add PUBLIC_API.md — core-vs-advanced split and stability contract"
```

---

## Final Verification (before finishing-a-development-branch)

After Task 2, confirm the whole branch is coherent:

```bash
uv run mypy --strict
uv run ruff check
uv run ruff format --check
PYTHONPATH=src uv run pytest tests/ -q
uv run python -c "from ooagent import OOAgent, AgentConfig, Query, Artifact; print('top-level import works')"
```

All must exit 0 / print the expected output. `git diff --stat` against the branch's base should show only: `src/ooagent/__init__.py` (modified), `tests/test_public_api.py` (new), `docs/PUBLIC_API.md` (new), `README.md` (one line added). No file under `src/ooagent/core/`, `adapters/`, `contexts/`, `plugins/`, `telemetry/`, or `workflow/`'s behavior should change — only `src/ooagent/__init__.py`'s content, which is purely additive re-exports of already-existing names.
