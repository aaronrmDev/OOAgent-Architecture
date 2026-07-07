# OOAgent — Architecture

> The deep-dive companion to [README.md](../README.md)'s golden path.
> Read this once you've run the examples and want to understand *why*
> the framework is built this way. For the authoritative, exhaustive
> contract (invariants, FSM, failure modes, extension protocol), see
> [CLAUDE.md](../CLAUDE.md).

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

See [CLAUDE.md](../CLAUDE.md) §4 for the full pattern-to-implementation mapping.

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
2. Write `CONTEXT.md` per the spec in [CLAUDE.md §14](../CLAUDE.md).
3. Write conformance tests (see [CLAUDE.md §17](../CLAUDE.md)).
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
