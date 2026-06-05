# OOAgent — Object-Oriented AI Agent Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5+-3178C6.svg)](https://www.typescriptlang.org/)

> A backend-agnostic, domain-agnostic AI agent framework governed by SOLID, GRASP, and GoF design patterns.
> Fork it, plug in your domain, wire your LLM, ship.

---

## Overview

OOAgent treats an AI agent as a **first-class software object**. Every response is the return value of a deterministic method call on an instantiated class — never ad-hoc generation.

The core is agnostic to both **inference backend** (Claude, GPT-4o, Gemini, Llama, Mistral, Ollama) and **problem domain** (engineering, finance, medicine, legal, etc.). Both are injected at construction time through stable interfaces.

---

## Architecture at a Glance

```
IAgent<TQuery, TResponse>
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
ooagent/
├── core/
│   ├── protocols.ts      # All interfaces & types (zero runtime dependencies)
│   ├── agent.ts          # OOAgent — Template Method implementation
│   ├── state.ts          # SessionState, FSM, Memento, Command log
│   ├── pipeline.ts       # ResponsePipeline (CoR), ConstraintEngine
│   ├── artifacts.ts      # ArtifactFactory, ProvenanceTracker, ResponseDecorator
│   ├── registry.ts       # ContextRegistry, ToolRegistry, PluginRegistry
│   ├── lifecycle.ts      # LifecycleManager, HealthStatus, CircuitBreaker
│   └── orchestrator.ts   # MultiAgentOrchestrator, SignalBus
│
├── adapters/
│   ├── llm/
│   │   ├── anthropic.ts  # ILLMClient → Anthropic Messages API
│   │   ├── openai.ts     # ILLMClient → OpenAI Chat API
│   │   ├── gemini.ts     # ILLMClient → Gemini API
│   │   ├── ollama.ts     # ILLMClient → Ollama (local)
│   │   └── caching_proxy.ts  # CachingLLMProxy (Proxy pattern)
│   └── tools/
│       ├── base.ts       # BaseTool abstract class
│       └── adapter.ts    # ToolAdapter (Adapter pattern)
│
├── contexts/
│   └── null_context.ts   # NullContext (Null Object — safe default)
│
├── plugins/
│   └── registry.ts       # PluginRegistry
│
├── telemetry/
│   ├── null_telemetry.ts # NullTelemetry (no-op — default)
│   └── console.ts        # ConsoleTelemetry (development)
│
└── testing/
    ├── stub_llm_client.ts  # Deterministic ILLMClient for unit tests
    ├── null_context.ts     # Re-exports NullContext
    └── fixtures.ts         # Common test doubles
```

---

## Quick Start

### 1. Install

```bash
npm install
npm run build
```

### 2. Wire an LLM backend

```typescript
import { OOAgent } from 'ooagent'
import { AnthropicLLMClient } from 'ooagent/adapters'

const agent = new OOAgent({
  llmClient: new AnthropicLLMClient({
    apiKey: process.env.ANTHROPIC_API_KEY!,
    model: 'claude-opus-4-8',
  }),
})

await agent.initialize({})
const response = await agent.respond({ text: 'Hello, agent.' })
await agent.dispose()
```

### 3. Plug in a domain context

```typescript
import { IDomainContext } from 'ooagent/core'
import { ContextRegistry } from 'ooagent/core'

class EngineeringContext implements IDomainContext {
  name    = 'Engineering'
  version = '1.0.0'
  // implement all 10 methods …
}

const registry = new ContextRegistry()
registry.register(new EngineeringContext())
```

### 4. Register tools

```typescript
import { ITool, BaseTool } from 'ooagent/adapters'

class SearchTool extends BaseTool {
  name        = 'search'
  description = 'Web search'
  inputSchema() { return { type: 'object', properties: { query: { type: 'string' } }, required: ['query'] } }
  async execute(args) { /* … */ }
}

agent.toolRegistry.register(new SearchTool())
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
4. Register: `contextRegistry.register(new MyContext())`.
5. No edits to `core/` — OCP enforced.

### Add a tool

1. Extend `BaseTool` or implement `ITool`.
2. Register: `toolRegistry.register(new MyTool())`.

### Add a new LLM backend

1. Implement `ILLMClient`.
2. Inject at construction: `new OOAgent({ llmClient: new MyClient() })`.

### Add a plugin

```typescript
class MyPlugin implements IPlugin {
  pluginId = 'my-plugin'
  version  = '1.0.0'
  onRegister(agent) { /* register tools / contexts */ }
  onDispose() { /* release resources */ }
  contributes() { return { tools: [new MyTool()] } }
}
pluginRegistry.register(new MyPlugin())
```

---

## Output Discipline

Every response is validated before emission:

- **Code** — complete, typed, runnable. No fill-in stubs. Explicit error paths.
- **Numbers** — every numeric claim carries `value + unit + SourceTag` (`measured | assumed | cited | derived`).
- **Recommendations** — falsifiable or measurable. No speculation.
- **Artifacts** — built exclusively via `ArtifactFactory`. Never free-form emission.
- **Invariants** — `ConstraintEngine.assertAll()` must pass before any artifact is emitted.

---

## Testing

```bash
npm test          # run jest suite
npm run typecheck # TypeScript strict check
```

The `testing/` package ships `StubLLMClient`, `NullTelemetry`, `NullContext`, and fixture factories for deterministic unit tests. Every `IAgent`, `IDomainContext`, `ITool`, `IPlugin`, and `ILLMClient` implementation must include a conformance test suite (see [CLAUDE.md §17](CLAUDE.md)).

---

## Scripts

| Command | Action |
|---|---|
| `npm run build` | Compile TypeScript to `dist/` |
| `npm run build:watch` | Watch mode compilation |
| `npm run typecheck` | Type-check without emit |
| `npm test` | Run jest test suite |

---

## License

MIT — Copyright © 2026 OOAgent Contributors.
