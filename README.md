# OOAgent — Object-Oriented AI Agent Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](https://www.python.org/)

> A backend-agnostic, domain-agnostic AI agent framework governed by SOLID, GRASP, and GoF design patterns.
> Fork it, plug in your domain, wire your LLM, ship.

---

## Overview

OOAgent treats an AI agent as a **first-class software object**. Every response is the return value of a deterministic method call on an instantiated class — never ad-hoc generation.

The core is agnostic to both **inference backend** (Claude, GPT-4o, Gemini, Llama, Mistral, Ollama) and **problem domain** (engineering, finance, medicine, legal, etc.). Both are injected at construction time through stable interfaces.

---

## Architecture at a Glance

```
IAgent[TQuery, TResponse]
└── AbstractAgent
    └── LLMAgent
        └── OOAgent  ← composition root
            ├── ILLMClient          (Anthropic / OpenAI / Gemini / Ollama)
            ├── ContextRegistry     (active IDomainContext)
            ├── ToolRegistry        (registered ITools)
            ├── PluginRegistry      (IPlugin extensions)
            ├── SessionState        (turn-level FSM + Memento)
            ├── LifecycleManager    (init / dispose / circuit-breaker)
            ├── ResponsePipeline    (Chain of Responsibility validation)
            ├── SolverDispatcher    (Strategy selector per ProblemClass)
            ├── ArtifactFactory     (Factory Method per output format)
            ├── ConstraintEngine    (invariant enforcement)
            ├── ProvenanceTracker   (source / citation discipline)
            ├── TelemetryProvider   (observability hook)
            └── ResponseDecorator   (final enrichment pass)
```

**Design philosophy:** composition over inheritance. `OOAgent` is a composition root, not a monolith. Each collaborator owns exactly one concern.

---

## Project Structure

```
src/ooagent/
├── core/
│   ├── protocols.py      # All interfaces & types (zero runtime dependencies)
│   ├── agent.py          # AbstractAgent, LLMAgent, OOAgent — Template Method implementation
│   ├── state.py          # SessionState, FSM, Memento, Command log
│   ├── pipeline.py       # ResponsePipeline (CoR), ConstraintEngine
│   ├── artifacts.py      # ArtifactFactory, ProvenanceTracker, ResponseDecorator
│   ├── registry.py       # ContextRegistry (Singleton), ToolRegistry, PluginRegistry
│   ├── lifecycle.py      # LifecycleManager, HealthStatus, CircuitBreaker
│   └── orchestrator.py   # MultiAgentOrchestrator, SignalBus
│
├── adapters/
│   ├── llm/
│   │   ├── anthropic.py  # ILLMClient → Anthropic Messages API
│   │   ├── openai.py     # ILLMClient → OpenAI Chat API
│   │   ├── gemini.py     # ILLMClient → Gemini API
│   │   ├── ollama.py     # ILLMClient → Ollama (local)
│   │   └── caching_proxy.py  # CachingLLMProxy, ThrottlingLLMProxy (Proxy pattern)
│   ├── tools/
│   │   ├── base.py       # BaseTool abstract class
│   │   └── adapter.py    # ToolAdapter (Adapter pattern)
│   └── data/             # IDataStore protocol + in-memory implementation
│
├── contexts/
│   └── null_context.py   # NullContext (Null Object — safe default)
│
├── plugins/
│   ├── base_plugin.py    # AbstractPlugin — reduces IPlugin boilerplate
│   └── logging/ audit/ cache/ rate_limit/ scope_guard/ security/ opentelemetry/ tool_kit/
│
└── telemetry/
    ├── null_telemetry.py # NullTelemetry (no-op — default)
    ├── otel.py           # OpenTelemetryProvider
    └── console.py        # ConsoleTelemetry (development)

tests/
├── core/ adapters/ plugins/  # Unit tests mirroring src/ooagent/
├── conformance/              # IAgent / IDomainContext / ITool / ILLMClient conformance suites
├── stub_llm_client.py        # Deterministic ILLMClient for unit tests
├── null_context.py           # Re-exports NullContext
└── fixtures.py                # Common test doubles
```

---

## Quick Start

### 1. Install

```bash
uv sync --extra dev --extra otel
```

### 2. Wire an LLM backend

```python
import asyncio
import os

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import AgentConfig, Query
from ooagent.adapters.llm.anthropic import AnthropicConfig, AnthropicLLMClient


async def main() -> None:
    agent = OOAgent(
        llm_client=AnthropicLLMClient(
            AnthropicConfig(api_key=os.environ["ANTHROPIC_API_KEY"], model="claude-opus-4-6"),
        ),
    )

    await agent.initialize(AgentConfig())
    response = await agent.respond(Query(text="Hello, agent."))
    await agent.dispose()


asyncio.run(main())
```

### 3. Plug in a domain context

```python
from ooagent.core.protocols import IDomainContext
from ooagent.core.registry import ContextRegistry


class EngineeringContext(IDomainContext):
    @property
    def name(self) -> str:
        return "Engineering"

    @property
    def version(self) -> str:
        return "1.0.0"

    # implement the remaining 10 methods …


registry = ContextRegistry.get_instance()
registry.register(EngineeringContext())
```

### 4. Register tools

```python
from typing import Any

from ooagent.adapters.tools.base import BaseTool
from ooagent.core.protocols import JSONSchema
from ooagent.core.registry import ToolRegistry


class SearchTool(BaseTool):
    name = "search"
    description = "Web search"

    def input_schema(self) -> JSONSchema:
        return {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}

    async def execute(self, args: dict[str, Any]) -> Any:
        self._validate_args(args)
        ...


tool_registry = ToolRegistry()
tool_registry.register(SearchTool())

agent = OOAgent(llm_client=..., tool_registry=tool_registry)
```

---

## Supported LLM Backends

| Backend   | Class                  | Notes                       |
|-----------|------------------------|-----------------------------|
| Anthropic | `AnthropicLLMClient`   | Claude 3/4 family           |
| OpenAI    | `OpenAILLMClient`      | GPT-4o, o-series            |
| Gemini    | `GeminiLLMClient`      | Gemini 1.5 / 2.0            |
| Ollama    | `OllamaLLMClient`      | Local models (Llama, Mistral, etc.) |

All backends implement `ILLMClient`. Swap them at construction — zero changes to core.

---

## Agent FSM

```
IDLE → GATHERING → MODELING → SOLVING → VALIDATING → DELIVERING → IDLE
                                  └──(any failure)──► FAILURE → DELIVERING → IDLE
```

Illegal FSM transitions raise `FSMViolation`. The FSM is owned by `SessionState`; no external object may mutate it directly.

---

## Design Patterns Applied

| Category | Patterns |
|----------|----------|
| **Behavioral** | Strategy, Chain of Responsibility, Observer, Template Method, Command, State, Visitor, Iterator, Mediator |
| **Creational** | Factory Method, Abstract Factory, Prototype, Singleton |
| **Structural** | Adapter, Decorator, Composite, Proxy, Bridge, Flyweight, Null Object |

See [CLAUDE.md](CLAUDE.md) §4 for the full pattern-to-implementation mapping.

---

## SOLID Compliance

| Principle | How OOAgent honors it |
|---|---|
| **SRP** | Each collaborator owns exactly one concern. Multi-concern requests are decomposed by `RequestController`. |
| **OCP** | Open to new backends, domains, tools, solvers, formats, and plugins via registered abstractions. Closed to modification. |
| **LSP** | Every `OOAgent` subtype satisfies `IAgent.respond()` with identical pre/postconditions. |
| **ISP** | Fine-grained interfaces: `IToolUser`, `IContextHost`, `IArtifactFactory` are independent. |
| **DIP** | Depends exclusively on abstractions (`ILLMClient`, `IDomainContext`, `ISolver`, `ITool`). No vendor SDK leaks into core. |

---

## Extending OOAgent

### Add a domain context

1. Implement `IDomainContext` (10 methods).
2. Write `CONTEXT.md` per the spec in [CLAUDE.md §14](CLAUDE.md).
3. Write conformance tests (see [CLAUDE.md §17](CLAUDE.md)).
4. Register: `context_registry.register(MyContext())`.
5. No edits to `core/` — OCP enforced.

### Add a tool

1. Extend `BaseTool` or implement `ITool`.
2. Register: `tool_registry.register(MyTool())`.

### Add a new LLM backend

1. Implement `ILLMClient`.
2. Inject at construction: `OOAgent(llm_client=MyClient())`.

### Add a plugin

```python
class MyPlugin(AbstractPlugin):
    plugin_id = "my-plugin"
    version = "1.0.0"

    def on_register(self, agent):
        ...  # register tools / contexts

    def on_dispose(self):
        ...  # release resources

    def contributes(self) -> PluginContributions:
        return PluginContributions(tools=[MyTool()])


plugin_registry.register(MyPlugin())
```

---

## Output Discipline

Every response is validated before emission:

- **Code** — complete, typed, runnable. No fill-in stubs. Explicit error paths.
- **Numbers** — every numeric claim carries `value + unit + SourceTag` (`measured | assumed | cited | derived`).
- **Recommendations** — falsifiable or measurable. No speculation.
- **Artifacts** — built exclusively via `ArtifactFactory`. Never free-form emission.
- **Invariants** — `ConstraintEngine.assert_all()` must pass before any artifact is emitted.

---

## Testing

```bash
uv run pytest         # run the pytest suite (pytest-asyncio, auto mode)
uv run mypy --strict  # strict type check
```

The `tests/` tree ships `StubLLMClient`, `NullTelemetry`, `NullContext`, and fixture factories for deterministic unit tests. Every `IAgent`, `IDomainContext`, `ITool`, `IPlugin`, and `ILLMClient` implementation must include a conformance test suite (see [CLAUDE.md §17](CLAUDE.md), and `tests/conformance/`).

---

## Scripts

| Command | Action |
|---|---|
| `uv sync --extra dev --extra otel` | Install runtime + dev + OpenTelemetry dependencies |
| `uv run mypy --strict` | Strict type check, no emit |
| `uv run ruff check` | Lint (import order, unused imports, upgrades) |
| `uv run pytest` | Run the test suite |
| `bash scripts/ai-safety-gate.sh --verbose` | Run the 13 AI Safety Guards |
| `bash scripts/conformance-check.sh` | Verify §17 conformance suites exist and pass |

---

## License

MIT — Copyright © 2026 OOAgent Contributors.
