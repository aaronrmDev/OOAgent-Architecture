# CLAUDE.md — OOAgent Generic Architecture
## Object-Oriented AI Agent Framework · MIT License

> **This file is the ground truth for any AI agent instantiated from this
> repository.** It is backend-agnostic: Claude, GPT-4o, Gemini, Llama, Mistral,
> or any future model can serve as the inference engine. The agent architecture
> does not change when the model changes.
>
> Fork this repo, drop in your `IDomainContext`, wire your LLM client, ship.

---

## 0. Purpose & License

```
MIT License — Copyright (c) 2026 OOAgent Contributors
Permission is granted to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of this software.
```

This file defines **what an OOAgent *is*** as a software object — its
contracts, invariants, extension points, and anti-patterns. It does **not**
define domain knowledge (that is the job of `IDomainContext` implementations).
The architecture is intentionally domain-agnostic and LLM-agnostic.

**Design philosophy:** An AI agent is a first-class software object governed
by the same engineering principles as any well-designed system. Every
response is the return value of a deterministic method call on an
instantiated class — never ad-hoc generation.

---

## 1. Class Hierarchy

```
IAgent<TQuery, TResponse>                          ← root interface (generic)
└── AbstractAgent<TQuery, TResponse>
    └── LLMAgent<TQuery, TResponse>
        └── OOAgent<TQuery, TResponse>             ← concrete root
            ├── implements ILifecycle
            ├── implements IConversationalObject
            ├── implements IToolUser
            ├── implements IContextHost<IDomainContext>
            ├── implements IObservable
            └── composes (all injected via constructor):
                ├── ILLMClient                     ← LLM backend adapter (DIP)
                ├── ContextRegistry                ← IoC: active IDomainContext
                ├── ToolRegistry                   ← IoC: registered ITools
                ├── PluginRegistry                 ← IoC: IPlugin extensions
                ├── SessionState<TState>           ← turn-level FSM + Memento
                ├── LifecycleManager               ← initialize / dispose / GC
                ├── ResponsePipeline               ← CoR validation chain
                ├── SolverDispatcher               ← Strategy selector
                ├── ArtifactFactory                ← Factory Method per format
                ├── ConstraintEngine               ← invariant enforcement
                ├── ProvenanceTracker              ← source / citation discipline
                ├── TelemetryProvider              ← observability (OCP hook)
                └── ResponseDecorator              ← final enrichment pass
```

**Composition over inheritance.** No god-class. Each collaborator owns exactly
one concern. `OOAgent` is a **composition root**, not a monolith.

---

## 2. SOLID — Applied to the Agent

| Principle | How `OOAgent` honors it |
|---|---|
| **SRP** | One response = one cohesive responsibility. Multi-concern requests are decomposed by `RequestController` into a sequence of single-purpose method calls. Each collaborator owns exactly one concern. |
| **OCP** | The agent is **open** to new backends (`ILLMClient`), domains (`IDomainContext`), tools (`ITool`), solvers (`ISolver`), formats (`IArtifactBuilder`), and plugins (`IPlugin`). It is **closed** to modification — all extension is via registered abstractions. |
| **LSP** | Every subtype of `OOAgent` — `SpecialistAgent`, `OrchestratorAgent`, `RecoveryAgent` — must satisfy `IAgent.respond(query) → response` with identical pre/postconditions and invariants. Subtypes may narrow preconditions or widen postconditions; never the reverse. |
| **ISP** | Interfaces are fine-grained. `IToolUser` is independent of `IContextHost`. `IArtifactFactory` is independent of `ILLMClient`. Callers depend only on the slice they need. |
| **DIP** | The agent depends exclusively on abstractions: `ILLMClient`, `IDomainContext`, `ISolver`, `ITool`, `IArtifactBuilder`, `IPlugin`. No concrete model, vendor, SDK, or schema leaks into the agent core. |

---

## 3. GRASP — Applied to the Agent

| Pattern | Application |
|---|---|
| **Information Expert** | The active `IDomainContext` is the expert on domain knowledge. The `ILLMClient` adapter is the expert on the model's wire protocol. Neither crosses into the other's territory. |
| **Creator** | `ArtifactFactory` is the sole creator of output artifacts. `PluginRegistry` is the sole creator of `IPlugin` instances. `ContextRegistry` is the sole creator of active `IDomainContext` bindings. |
| **Controller** | `RequestController` orchestrates the full turn: `parse → classify → validate → dispatch → solve → build → decorate → emit`. No other object orchestrates the turn flow. |
| **Low Coupling** | Domain modules depend only on `IDomainContext`. The agent core depends only on its interface contracts. The LLM backend is behind `ILLMClient`. No module imports a sibling's concrete class. |
| **High Cohesion** | Every method does one thing at one abstraction level. `ConstraintEngine.assert_all()` only validates. `ProvenanceTracker.record()` only records. No method mixes concerns. |
| **Polymorphism** | `solve(problem)` dispatches by `ProblemClass` declared by the active context. `build(format)` dispatches by `ArtifactFormat`. Both use runtime polymorphism, not `if/elif` chains. |
| **Pure Fabrication** | `ConstraintEngine`, `ProvenanceTracker`, `TelemetryProvider`, `ResponseDecorator`, `SignalBus` — invented helpers with no real-world counterpart; they exist to keep cohesion high and coupling low. |
| **Indirection** | `LLMAdapter` mediates between `Intent` objects and raw vendor API payloads. `ToolAdapter` mediates between tool invocations and vendor-specific tool-call schemas. |
| **Protected Variations** | A stable `IAgent<TQuery, TResponse>` surface insulates all callers from internal refactors, model upgrades, solver swaps, or context changes. |

---

## 4. GoF Patterns — Runtime Behavior

| Pattern | Concrete use in `OOAgent` |
|---|---|
| **Strategy** | Solver selection per `ProblemClass`. `SolverDispatcher` holds a registry of `ISolver` implementations; the active `IDomainContext` declares which solver to use. |
| **Chain of Responsibility** | `ResponsePipeline`: `parse → schema → units → range → feasibility → invariants → domain_steps`. Each link passes or halts with `ConstraintViolation`. |
| **Observer** | `SessionState` notifies subscribers (calculations, telemetry, decorators) on every FSM transition and on `commit()`. |
| **Factory Method** | `ArtifactFactory.build(format)` dispatches to format-specific builders: `.py / .ts / .md / .json / .sql / .html / .yaml / mermaid`. |
| **Abstract Factory** | `ContextFactory.load(domain)` instantiates a complete domain stack: context + solvers + invariants + pipeline. |
| **Adapter** | `LLMAdapter` translates `CompletionRequest` objects into vendor-specific API payloads (Anthropic, OpenAI, Gemini, Ollama). `ToolAdapter` wraps `ITool` in vendor tool-call schemas. |
| **Decorator** | `ResponseDecorator` appends citations, unit assertions, sensitivity brackets, and provenance **after** the solver returns — without modifying the solver. |
| **Command** | Each agent action is a reified `Command` object: serialisable, replayable, auditable. The command log is the source of truth for session history. |
| **State** | Agent FSM: `idle → gathering → modeling → solving → validating → delivering → idle`. Transitions are explicit; illegal transitions raise `FSMViolation`. |
| **Template Method** | `respond()` is the abstract template. Concrete steps come from the active `IDomainContext.pipeline()`. The skeleton never changes; the steps do. |
| **Composite** | Hierarchical artifacts (multi-file codebases, nested reports) and tree-shaped problems are walked uniformly via `IArtifactNode`. |
| **Memento** | `SessionState.snapshot()` captures FSM state + scratch space. `restore(id)` rolls back for retry or error recovery. |
| **Singleton** | `ConstraintEngine` and `ContextRegistry` — single sources of truth per process. Exposed only through their interfaces; tests can reset via `.reset()`. |
| **Visitor** | Cross-cutting operations (cost estimation, sensitivity analysis, what-if sweeps) applied via `IVisitor` across heterogeneous artifact node trees. |
| **Iterator** | Uniform traversal over result sets, parameter sweeps, tool output streams, and streaming LLM response chunks. |
| **Mediator** | `RequestController` mediates between `Parser`, `SolverDispatcher`, `ConstraintEngine`, `ArtifactFactory`, and `ResponseDecorator` — collaborators never call each other directly. |
| **Null Object** | `NullContext` answers safely when no domain is loaded. `NullTelemetry` is a no-op `ITelemetryProvider` for environments without observability. |
| **Prototype** | New `Command` and `Artifact` instances are cloned from registered prototypes via `IPrototypable.clone()`. |
| **Flyweight** | Shared `Term` and `ProblemClass` instances across context variants — immutable, interned at startup. |
| **Proxy** | `CachingLLMProxy` wraps `ILLMClient` to cache deterministic completions. `ThrottlingLLMProxy` enforces rate limits transparently. |
| **Bridge** | `ArtifactRenderer` separates the artifact abstraction (what it contains) from its rendering format (how it is serialised). |

---

## 5. Core Interface Catalog

Every interface is generic, dependency-free, and implementable in any typed
language (Python, TypeScript, Go, Rust, Java, C#, etc.). The canonical
implementation lives in `src/ooagent/core/protocols.py`; the shapes below are
that file's public surface.

```python
# ── ABC notation — mirrors src/ooagent/core/protocols.py ────────────────────

class IAgent(ABC, Generic[TQuery, TResponse]):
    @abstractmethod
    async def respond(self, query: TQuery) -> TResponse: ...

    @property
    @abstractmethod
    def agent_id(self) -> str: ...

    @property
    @abstractmethod
    def state(self) -> "ISessionState": ...


class ILLMClient(ABC):
    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    @abstractmethod
    def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]: ...

    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @property
    @abstractmethod
    def vendor(self) -> LLMVendor: ...

    @property
    @abstractmethod
    def max_tokens(self) -> int: ...

    @property
    @abstractmethod
    def supports_tools(self) -> bool: ...


class IDomainContext(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    def vocabulary(self) -> set[Term]: ...

    @abstractmethod
    def problem_classes(self) -> set[ProblemClass]: ...

    @abstractmethod
    def solvers(self) -> dict[str, "ISolver"]: ...

    @abstractmethod
    def invariants(self) -> list[Invariant]: ...

    @abstractmethod
    def pipeline(self) -> list[PipelineStep]: ...

    @abstractmethod
    def anti_patterns(self) -> list[AntiPattern]: ...

    @abstractmethod
    def required_inputs(self, pc: ProblemClass) -> list[InputSpec]: ...

    @abstractmethod
    def artifact_preferences(self) -> ArtifactPolicy: ...

    @abstractmethod
    def system_prompt_extension(self) -> str: ...

    @abstractmethod
    def resolve_intent(self, query: Query) -> ProblemClass | None: ...


class ISolver(ABC):
    @abstractmethod
    def can_solve(self, problem_class: str) -> bool: ...

    @abstractmethod
    async def solve(self, query: Query, ctx: IDomainContext) -> Solution: ...


class ITool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def input_schema(self) -> JSONSchema: ...

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> Any: ...

    @abstractmethod
    def to_vendor_spec(self, vendor: LLMVendor) -> VendorToolSpec: ...


class IPlugin(ABC):
    @property
    @abstractmethod
    def plugin_id(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    def on_register(self, agent: "IAgent[Any, Any]") -> None: ...

    @abstractmethod
    def on_dispose(self) -> None: ...

    @abstractmethod
    def contributes(self) -> PluginContributions: ...  # tools | contexts | solvers | decorators


class ILifecycle(ABC):
    @abstractmethod
    async def initialize(self, config: AgentConfig) -> None: ...

    @abstractmethod
    async def health_check(self) -> HealthStatus: ...

    @abstractmethod
    async def dispose(self) -> None: ...  # releases all managed resources

    @property
    @abstractmethod
    def is_ready(self) -> bool: ...


class ISessionState(ABC):
    @property
    @abstractmethod
    def fsm(self) -> AgentFSMState: ...

    @property
    @abstractmethod
    def turn(self) -> int: ...

    @property
    @abstractmethod
    def context_name(self) -> str: ...

    @property
    @abstractmethod
    def trace(self) -> FSMTrace: ...

    @abstractmethod
    def transition(self, to: AgentFSMState) -> None: ...

    @abstractmethod
    def set_context(self, name: str) -> None: ...

    @abstractmethod
    def snapshot(self) -> Memento: ...

    @abstractmethod
    def restore(self, id: str) -> None: ...

    @abstractmethod
    def commit(self, cmd: Command) -> None: ...

    @abstractmethod
    def subscribe(self, obs: StateObserver) -> Unsubscribe: ...

    @abstractmethod
    async def flush(self) -> None: ...

    @abstractmethod
    def reset(self) -> None: ...


class ITelemetryProvider(ABC):
    @abstractmethod
    async def span(self, name: str, fn: Callable[[], Awaitable[T]]) -> T: ...

    @abstractmethod
    def counter(self, name: str, delta: float = 1) -> None: ...

    @abstractmethod
    def gauge(self, name: str, value: float) -> None: ...

    @abstractmethod
    def histogram(self, name: str, value: float) -> None: ...

    @abstractmethod
    def event(self, name: str, payload: dict[str, Any]) -> None: ...


class IArtifactFactory(ABC):
    @abstractmethod
    def build(
        self, solution: Solution, format: ArtifactFormat, policy: ArtifactPolicy
    ) -> Artifact: ...

    @abstractmethod
    def build_error(self, violation: str, ctx: str) -> Artifact: ...

    @abstractmethod
    def build_missing_inputs(self, missing: list[InputSpec], ctx: str) -> Artifact: ...

    @abstractmethod
    def build_scope_exit(self, ctx: str, query: str) -> Artifact: ...


class IOrchestrator(ABC):
    @abstractmethod
    async def dispatch(self, query: Query, contexts: list[IDomainContext]) -> list[Solution]: ...

    @abstractmethod
    async def synthesize(self, solutions: list[Solution], original: Query) -> Solution: ...
```

---

## 6. Lifecycle & Resource Management

The `LifecycleManager` is the agent's resource owner. It is the OOP analogue
of a garbage collector: it tracks every resource the agent allocates, ensures
orderly release, and prevents leaks across turns.

```
Lifecycle phases:
  UNINITIALIZED
    │  initialize(config)          ← allocate LLM client, registries, state
    ▼
  READY
    │  respond(query)              ← normal turn execution
    ▼  (repeats)
  READY
    │  dispose()                   ← release client connections, flush telemetry,
    ▼                                 persist command log, clear caches
  DISPOSED

LifecycleManager responsibilities:
  1. Ordered initialization:   config → LLM client → registries → plugins → state
  2. Health checks:            ILLMClient.ping(), PluginRegistry.verify()
  3. Graceful dispose:         plugins.onDispose() → state.flush() → client.close()
  4. Resource guards:          refuse respond() if !isReady; refuse dispose() if UNINITIALIZED
  5. Finalizer registration:   register dispose() with process exit handlers
  6. Timeout enforcement:      per-turn and per-tool-call timeout budgets
  7. Memory pressure:          evict LRU Memento entries when SessionState exceeds max size
  8. Circuit breaker:          after N consecutive ILLMClient failures → DEGRADED state
```

**Rule:** every object that holds an external resource (`ILLMClient`,
file handle, network connection, cache) must implement `ILifecycle` and must
be registered with `LifecycleManager` at construction time.

---

## 7. Package & Project Structure

```
src/ooagent/
├── core/
│   ├── protocols.py          # All interface + type definitions (zero dependencies)
│   ├── agent.py              # AbstractAgent, LLMAgent, OOAgent — composition root, Template Method
│   ├── state.py              # SessionState, FSM, Memento, Command
│   ├── pipeline.py           # ResponsePipeline (CoR), ConstraintEngine
│   ├── artifacts.py          # ArtifactFactory, ProvenanceTracker, ResponseDecorator
│   ├── registry.py           # ContextRegistry (Singleton), ToolRegistry, PluginRegistry
│   ├── lifecycle.py          # LifecycleManager, HealthStatus, CircuitBreaker
│   └── orchestrator.py       # MultiAgentOrchestrator, SignalBus
│
├── adapters/
│   ├── llm/
│   │   ├── anthropic.py      # ILLMClient → Anthropic Messages API
│   │   ├── openai.py         # ILLMClient → OpenAI Chat API
│   │   ├── gemini.py         # ILLMClient → Gemini API
│   │   ├── ollama.py         # ILLMClient → Ollama (local)
│   │   └── caching_proxy.py  # CachingLLMProxy, ThrottlingLLMProxy (Proxy pattern)
│   ├── tools/
│   │   ├── base.py           # BaseTool abstract class
│   │   └── adapter.py        # ToolAdapter (Adapter pattern)
│   └── data/                 # IDataStore protocol + in-memory implementation
│
├── contexts/
│   ├── null_context.py       # NullContext (Null Object)
│   └── [domain]/             # User-supplied IDomainContext implementations
│       └── CONTEXT.md        # Domain specification (see §14)
│
├── plugins/
│   ├── base_plugin.py        # AbstractPlugin — reduces IPlugin boilerplate
│   ├── logging/ audit/ cache/ rate_limit/ scope_guard/ security/ opentelemetry/
│   ├── tool_kit/              # CalculatorTool, DatetimeTool, HttpFetchTool
│   └── [plugin-name]/        # User-supplied IPlugin implementations
│
├── telemetry/
│   ├── null_telemetry.py     # NullTelemetry (Null Object — default)
│   ├── otel.py               # OpenTelemetryProvider (ITelemetryProvider)
│   └── console.py            # ConsoleTelemetry (development)
│
├── workflow/                 # IDeliveryWorkflow — SpecDrivenWorkflow layer (see §24)
│   ├── spec_driven.py        # SpecDrivenWorkflow — sole IDeliveryWorkflow implementation
│   ├── constitution.py       # 8-Article constitution (machine-readable ARTICLES)
│   ├── gate_catalog.py       # 19-target gate catalog (GATE_TARGETS)
│   └── traceability.py       # Orphan-detection logic for spec → task → test → code
│
└── mcp/                      # OOAgent as an MCP (Model Context Protocol) server — see docs/MCP.md
    ├── config.py              # env-var → OOAgent construction (vendor/API-key dispatch)
    └── server.py              # FastMCP server: respond tool, contexts resource, entry point

tests/
├── core/ adapters/ plugins/   # Unit tests mirroring src/ooagent/ package-for-package
├── conformance/               # IAgent / IDomainContext / ITool / ILLMClient conformance suites (§17)
├── workflow/                  # SpecDrivenWorkflow unit + traceability tests
├── mcp/                       # MCP server config/integration tests
├── stub_llm_client.py         # Deterministic ILLMClient for unit tests
├── null_context.py            # Re-exports NullContext
└── fixtures.py                 # Common Query/Solution/Artifact test doubles
```

**Package management rules:**
- `core/protocols.py` has **zero runtime dependencies** — only stdlib (`abc`, `dataclasses`, `typing`) imports.
- `core/` depends only on `core/protocols.py`. No adapter, no context, no plugin.
- `adapters/` depends on `core/` and external packages (`httpx`, `opentelemetry-*`) — never on `contexts/` or `plugins/`.
- `contexts/` depends on `core/protocols.py` only.
- `plugins/` depends on `core/protocols.py` + any `adapters/` they need.
- `workflow/` depends on `core/protocols.py` only (`IDeliveryWorkflow` is a peer layer — §24 — never on `core/agent.py` or any other package).
- `mcp/` depends on `core/`, `contexts/null_context.py`, `adapters/llm/*`, and the external `mcp` SDK package — never on `plugins/` or `workflow/`.
- Circular imports are caught by `mypy --strict` and `ruff` (import-sort/unused-import rules) in CI.
- Every package exports its public surface via `__init__.py`.
- Versioning: `core/` is semver-stable. Breaking changes to `IAgent`, `IDomainContext`,
  or `ILLMClient` require a major version bump.

---

## 8. Inheritance & Specialization Guide

### 8a. Specializing the Agent

```python
# Extend OOAgent only to override a single Template Method step.
# Never override respond() directly.

class StreamingAgent(OOAgent):
    """Overrides only the solve step to use streaming."""

    async def _solve(
        self, query: Query, context: IDomainContext, extras: dict[str, Any]
    ) -> Solution:
        # use ILLMClient.stream() instead of .complete()
        ...


class CachedAgent(OOAgent):
    """Inject a CachingLLMProxy at construction — no subclassing needed.
    Prefer composition (Proxy) over inheritance for cross-cutting concerns."""


class EmbeddedAgent(LLMAgent[EmbeddedQuery, EmbeddedResponse]):
    """OOAgent itself is already concretely typed as LLMAgent[Query, Artifact]
    (see core/agent.py) — to narrow TQuery/TResponse for a specialized
    query/response pair, subclass LLMAgent directly rather than OOAgent."""
```

**Rule:** prefer composition + injection over inheritance. Subclass only when
you need to override a protected Template Method step. Every subclass must
satisfy LSP: same preconditions, same postconditions, same invariants.

### 8b. Specializing the Context

```python
class MyDomainContext(IDomainContext):
    @property
    def name(self) -> str:
        return "MyDomain"

    @property
    def version(self) -> str:
        return "1.0"

    # Implement the remaining 10 methods (vocabulary, problem_classes, solvers,
    # invariants, pipeline, anti_patterns, required_inputs,
    # artifact_preferences, system_prompt_extension, resolve_intent).
    # Ship this in contexts/my_domain/ with a CONTEXT.md.
```

**Rule:** contexts are **closed for modification, open for composition**.
If two domains partially overlap, compose them:

```python
class HybridContext(IDomainContext):
    def __init__(self, a: IDomainContext, b: IDomainContext) -> None:
        self._a = a
        self._b = b

    def vocabulary(self) -> set[Term]:
        return self._a.vocabulary() | self._b.vocabulary()

    def invariants(self) -> list[Invariant]:
        return [*self._a.invariants(), *self._b.invariants()]

    # etc. — merge, not override
```

### 8c. Specializing Tools

```python
class MyTool(BaseTool):
    name = "my_tool"
    description = "..."

    def input_schema(self) -> JSONSchema:
        return {...}

    async def execute(self, args: dict[str, Any]) -> Any:
        self._validate_args(args)  # BaseTool helper — checks input_schema()'s "required" fields
        # Raise ToolExecutionError on failure — never return error strings.
        # Be idempotent where possible.
        ...

    # to_vendor_spec() is provided by BaseTool for anthropic/openai/gemini/ollama.
    # Override only if a vendor needs behavior BaseTool doesn't already cover.
```

### 8d. Plugin Contributions

```python
class MyPlugin(AbstractPlugin):
    plugin_id = "my-plugin"
    version = "1.0.0"

    def on_register(self, agent: "IAgent[Any, Any]") -> None:
        # Register tools, contexts, solvers, or decorators here.
        # Never hold a strong reference to agent — use weakref.ref if needed.
        ...

    def on_dispose(self) -> None:
        # Release all resources this plugin allocated.
        # Must be idempotent — may be called multiple times.
        ...

    def contributes(self) -> PluginContributions:
        return PluginContributions(
            tools=[MyTool()],
            contexts=[MyDomainContext()],
        )
```

---

## 9. DIP Boundary — IDomainContext Plug Point

The agent declares the contract; the context fulfills it. The boundary is
absolute: nothing on the agent side knows about a specific domain; nothing
on the context side knows about agent internals.

```
┌─────────────────────────────────────────┐
│              OOAgent core               │
│                                         │
│   depends on IDomainContext (abstract)  │
└───────────────────┬─────────────────────┘
                    │  <<Protocol / Interface>>
                    │  IDomainContext
                    │
        ┌───────────┼──────────────┐
        │           │              │
  NullContext  EngineeringCtx  FinanceCtx  ...
  (built-in)   (user-supplied)  (user-supplied)
```

**Exactly one** `IDomainContext` is active per turn (resolved by
`ContextRegistry`). `NullContext` is the default when no match is found.

**Context resolution algorithm** (pluggable — override `ContextRegistry.resolve()`):
1. Tokenize query text.
2. Score each registered context by vocabulary + problem-class keyword overlap.
3. Boost score if `context.resolveIntent(query)` returns a non-null `ProblemClass`.
4. Return highest scorer above threshold; fall back to `NullContext`.
5. Threshold and scoring weights are configurable per `IAgentConfig`.

---

## 10. Response Protocol (Template Method)

```python
async def respond(self, query: Query) -> Artifact:
    """Template Method — §10 CLAUDE.md."""
    # Pre-condition: is_ready is True
    # Post-condition: returns non-null Artifact; SessionState.turn incremented
    if not self._lifecycle.is_ready:
        raise LifecycleError("Agent is not ready. Call initialize() first.")

    async def _turn() -> Artifact:
        self._provenance.clear()
        self._state.transition("GATHERING")

        try:
            context = self._ctx_registry.resolve(query)           # IDomainContext
            self._state.set_context(context.name)
            pipeline = self._pipeline.extend(context.pipeline())  # CoR
            snapshot = self._state.snapshot()                     # Memento
        except Exception as err:
            # `context` has not been resolved yet at this point, so there is
            # no IDomainContext to pass into _handle_failure(err, context,
            # snapshot.id) — an argument-availability problem, not an FSM
            # legality problem (GATHERING → FAILURE is a legal transition
            # per VALID_TRANSITIONS in state.py).
            return self._handle_unrecoverable_failure(err, None)

        # MODELING: validate query
        self._state.transition("MODELING")
        try:
            extras = await pipeline.run(query, context)
        except Exception as err:
            return self._handle_failure(err, context, snapshot.id)
        # ConstraintViolation → FSM.FAILURE → emit error artifact → return

        # SOLVING: LLM + tool loop
        self._state.transition("SOLVING")
        try:
            solution = await self._solve(query, context, extras)
        except Exception as err:
            return self._handle_failure(err, context, snapshot.id)
        # ScopeExitError → FSM.FAILURE → emit scope-exit artifact → return

        # VALIDATING: domain invariants
        self._state.transition("VALIDATING")
        try:
            self._constraint_engine.assert_all(solution, context.invariants())
        except Exception as err:
            return self._handle_failure(err, context, snapshot.id)
        # ConstraintViolation → FSM.FAILURE → emit violation artifact → return

        # DELIVERING: build + decorate artifact
        self._state.transition("DELIVERING")
        try:
            format = query.format or (context.artifact_preferences().preferred_formats or ["text"])[0]
            artifact = self._artifact_factory.build(solution, format, context.artifact_preferences())
            enriched = self._decorator.apply(artifact, self._provenance.dump())

            cmd = Command(
                id=str(uuid.uuid4()),
                query=query,
                solution=solution,
                context_name=context.name,
                trace=self._state.trace,
                timestamp=time.time(),
            )
            self._state.commit(cmd)
            self._state.reset()                                   # → FSM.IDLE

            self._telemetry.event(
                "turn.complete",
                {"context": context.name, "format": format, "turn": self._state.turn},
            )

            self._lifecycle.record_llm_success()
            return enriched
            # Invariants: FSM == IDLE; turn incremented by 1; provenance cleared
        except Exception as err:
            # DELIVERING's only legal exit is IDLE (no FAILURE transition
            # defined for it either) — same unconditional recovery path as
            # the GATHERING prelude above. Added during this port's own code
            # review; a real improvement over the original TS design, which
            # had no recovery path for failures in these two phases.
            return self._handle_unrecoverable_failure(err, context)

    return await self._telemetry.span("agent.turn", _turn)
```

**No step is skipped. No emission occurs without `assert_all` passing.**

---

## 11. Design by Contract

Every method declares:

- **Preconditions** — required inputs, valid types, value ranges, lifecycle state.
- **Postconditions** — guaranteed output shape, FSM state, side effects.
- **Invariants** — conditions that hold before and after every method call:

```
Generic invariants (always on, regardless of active context):
  ✓ Output language matches query language.
  ✓ Every numeric claim carries a unit AND a SourceTag
    (measured | assumed | cited | derived).
  ✓ Every recommendation is falsifiable or measurable.
  ✓ No artifact is emitted without passing ConstraintEngine.assertAll().
  ✓ No domain claim is made when NullContext is active.
  ✓ FSM is in IDLE state before and after each complete turn.
  ✓ SessionState.turn increments by exactly 1 per successful turn.
  ✓ ProvenanceTracker is cleared at the start of every turn.
  ✓ All registered plugins are in READY state before any turn.

Domain invariants: supplied by IDomainContext.invariants().

Violation protocol:
  → raise ConstraintViolation(invariant, offendingValue, inputs)
  → NEVER silent-fix. NEVER round away a violation.
  → Halt, emit violation report, reset FSM to IDLE.
```

---

## 12. Agent FSM

```
             ┌──────────┐
        ┌───►│   IDLE   │◄────────────────────────┐
        │    └────┬─────┘                         │
        │         │ query received                │
        │    ┌────▼─────┐  missing context        │
        │    │ GATHERING├──────────────────────►  │
        │    └────┬─────┘                 ┌───────┤
        │         │ context resolved      │FAILURE│
        │    ┌────▼─────┐                 └───┬───┤
        │    │ MODELING ├──constraint violation│   │
        │    └────┬─────┘                     │   │
        │         │ pipeline passed        ◄──┘   │
        │    ┌────▼─────┐                         │
        │    │ SOLVING  ├──scope exit             │
        │    └────┬─────┘      │                  │
        │         │        ┌───▼───┐              │
        │    ┌────▼──────┐ │FAILURE├──────────────►
        │    │ VALIDATING│ └───────┘
        │    └────┬──────┘
        │         │ all invariants pass
        │    ┌────▼──────┐
        └────┤ DELIVERING│
             └───────────┘
```

**Rules:**
- Transitions not in the table above raise `FSMViolation`.
- `FAILURE` always leads to `DELIVERING` (emit error artifact) then `IDLE`.
- `AWAITING` (missing required input) is a valid intermediate state between
  `GATHERING` and `MODELING` — the agent emits an input checklist and waits.
- The FSM is owned by `SessionState`. No external object may mutate it directly.

---

## 13. Multi-Agent Orchestration

```
MultiAgentOrchestrator
  │
  ├── decompose(query) → SpecialistTask[]        # one task per context
  │
  ├── dispatch(tasks) → Promise.all(             # parallel execution
  │     tasks.map(t => specialistAgent(t))       # each is a full OOAgent
  │   )                                          # bounded by concurrency semaphore
  │
  ├── SignalBus.publish(specialist.done, sol)    # Mediator — no direct coupling
  │
  └── synthesize(solutions, originalQuery)       # meta-agent LLM call
        → Solution                               # or naive concat if no meta-agent

Concurrency contract:
  - Each specialist runs in its own OOAgent instance (no shared mutable state).
  - SignalBus is the only shared object; it is concurrency-safe.
  - Semaphore bounds parallel API calls (default: 5; configurable).
  - Failures in one specialist do not cancel others (unless failFast: true).
  - Synthesis always runs after all specialists complete or timeout.

Timeout contract:
  - Per-specialist timeout: IAgentConfig.specialistTimeoutMs (default: 30 000).
  - Total orchestration timeout: IAgentConfig.orchestrationTimeoutMs (default: 120 000).
  - Timed-out specialists contribute an error Solution; synthesis proceeds.
```

---

## 14. CONTEXT.md Specification (Domain Extension Contract)

Every `IDomainContext` implementation **must** ship a `CONTEXT.md` alongside
its source code. This file is the contract between the domain author and the
agent runtime. Minimum required sections:

```markdown
# [DomainName] Context — v[X.Y]

## 1. Scope
What problem classes this context handles. What it explicitly does NOT handle.

## 2. Vocabulary (canonical terms)
Table: Term | Definition | Canonical?

## 3. Problem Classes
Table: Name | Description | Required Inputs | Solver

## 4. Invariants
List: Name | Condition | Severity | Rationale

## 5. Anti-Patterns
List: Name | Pattern | Why Forbidden

## 6. Stack Defaults (if applicable)
What technologies/libraries are assumed unless overridden.

## 7. Artifact Preferences
Preferred formats, type-hint requirements, comment policy.

## 8. System Prompt Extension
The exact text injected into the LLM system prompt when this context is active.

## 9. Extension Points
How users should subclass or compose this context.

## 10. Known Limitations
What this context cannot do. Where NullContext should be preferred.
```

---

## 15. Output Discipline

The agent enforces these output rules regardless of domain context:

```
Code:
  - Complete, typed, runnable blocks only. No fill-in stubs.
  - Full type hints (TypeScript / Python) end-to-end.
  - Explicit error paths in every non-trivial function.
  - Default algorithmic complexity ≤ O(n); annotate deviations.
  - Comments only for non-obvious logic. Self-explanatory code → 0 comments.
  - File headers: "# filename.ext". Function headers: "## FunctionName".
  - No hard-coded secrets. Environment variables for all config.

Prose:
  - ≤ 50 words per block when the active context defines a prose limit.
  - Zero conversational filler (no greetings, apologies, restatements).
  - Lists in natural language when ≤ 3 items.

Numeric claims:
  - Every number carries: value + unit + SourceTag.
  - SourceTag ∈ { measured | assumed | cited | derived }.
  - Sensitivity bracket when uncertainty is relevant: value ± δ [unit] (SourceTag).

Diagrams:
  - Mermaid for flow / sequence / class diagrams.
  - ASCII for quick inline schematics.
  - Chart.js / D3 for quantitative data series.

Citations:
  - Only when grounded in fetched or primary sources.
  - Format: [Title](URL) [SourceTag].
  - Decorative citations are forbidden.

Formulas:
  - Render symbolically first, then substitute numerics.
  - Example: E = mc² → E = (1 kg)(3×10⁸ m/s)² = 9×10¹⁶ J (derived).
```

---

## 16. Failure Modes

| Failure | Response |
|---|---|
| Insufficient data | Emit ordered checklist from `context.requiredInputs(pc)`. Do not guess. Transition to `AWAITING`. |
| Conflicting inputs | Surface the conflict explicitly. Propose reconciliation options. Request a decision. |
| Out-of-domain query | Declare scope exit. Activate `NullContext`. Do not fake expertise. List which contexts would satisfy the query. |
| No context loaded | State that `NullContext` is active. List registered context names and their declared scopes. |
| LLM client failure | Log via `ITelemetryProvider`. Retry up to `config.maxRetries` with exponential backoff. After exhaustion: emit degraded response with explicit `[LLMError]` prefix. |
| Tool execution error | Catch `ToolExecutionError`. Log tool name, args, and error. Continue the turn without the tool result; note the failure in the response. |
| Invariant violation | Halt. Emit `ConstraintViolation` report with: invariant name, offending value, inputs that produced it. FSM → FAILURE → DELIVERING → IDLE. |
| Plugin failure | Isolate in `onRegister`/`onDispose`. Log. Disable the plugin. Do not crash the agent. |
| Context resolution tie | Log the tie. Pick the highest-version context. Emit a `[ContextAmbiguous]` notice in the response. |
| FSM violation | Raise `FSMViolation`. Log full FSM trace. Reset to IDLE. This is always a programming error — never a user error. |
| Token budget exceeded | Truncate the tool loop at `config.maxToolRounds`. Emit partial response with `[TokenBudgetExceeded]` notice. |

---

## 17. Testing Contracts

Every implementation of `IAgent`, `IDomainContext`, `ITool`, `IPlugin`, and
`ILLMClient` must ship a conformance test suite that verifies the following:

```
IAgent conformance:
  ✓ respond(emptyQuery) → ConstraintViolation artifact (not throw)
  ✓ FSM is IDLE before and after every successful turn
  ✓ SessionState.turn increments by exactly 1 per turn
  ✓ dispose() is idempotent (call twice → no error)
  ✓ respond() after dispose() → throws LifecycleError

IDomainContext conformance:
  ✓ vocabulary() returns non-empty set
  ✓ problemClasses() returns non-empty set
  ✓ invariants() are callable without throwing
  ✓ resolveIntent(nullQuery) returns null (not throws)
  ✓ artifactPreferences().preferredFormats is non-empty

ITool conformance:
  ✓ execute(validArgs) returns without throwing
  ✓ execute(invalidArgs) throws ToolExecutionError (not silent fail)
  ✓ toVendorSpec() is valid JSON for all supported vendors
  ✓ execute() is deterministic given the same args (if documented as pure)

ILLMClient conformance (use StubLLMClient for unit tests):
  ✓ complete(validRequest) returns CompletionResponse
  ✓ complete(oversizedRequest) throws TokenLimitError
  ✓ stream() yields at least one chunk before resolving

Test doubles:
  - StubLLMClient:  scripted responses keyed by message content pattern.
  - NullTelemetry:  no-op implementation — use in all unit tests.
  - NullContext:    built-in; use as baseline for agent-level tests.
  - ClockMock:      injectable clock for FSM timeout tests.
```

---

## 18. Versioning Strategy

```
core/protocols.*    MUST be semver-stable.
                    Breaking change to any interface → major version bump.
                    Additive change → minor version bump.
                    Bug fix → patch version bump.

IDomainContext impls version independently (version field on the interface).
                    Contexts declare their own semver in context.version.
                    ContextRegistry resolves ties by version (higher wins).

IPlugin             Plugin version declared in pluginId + version fields.
                    PluginRegistry rejects duplicate (pluginId, version) pairs.
                    Plugins declare compatible agent core version range.

ILLMClient adapters version with their underlying SDK.
                    Adapters expose modelId; agent logs it in every Command.

Command log         Is the audit trail; never delete or mutate historic Commands.
                    Commands are append-only; schema migration is additive.
```

---

## 19. Language Policy

- Respond in the user's language.
- Canonical technical terms remain in their canonical form.
- The active `IDomainContext` defines which terms are canonical for its domain.
- When emitting code, use the conventions of the target language (snake_case
  for Python, camelCase for TypeScript, etc.) regardless of the query language.

---

## 20. Pre-Emission Self-Check

Before emitting any response, verify internally:

```
[ ] Active IDomainContext identified (or NullContext declared)
[ ] ILifecycle.isReady === true
[ ] Single responsibility honored (SRP) — one concern per artifact
[ ] Zero filler tokens
[ ] Every numeric claim: value + unit + SourceTag
[ ] Every recommendation: falsifiable or measurable
[ ] Output format matches request + artifactPreferences()
[ ] Generic invariants (§11) satisfied
[ ] Domain invariants (context.invariants()) satisfied
[ ] Domain pipeline (context.pipeline()) followed, or deviation logged
[ ] No cross-domain leakage between contexts
[ ] Artifact built via ArtifactFactory — never free-form emission
[ ] Provenance recorded for every external claim
[ ] FSM is in IDLE at end of turn
[ ] LifecycleManager has no unresolved dispose() callbacks
```

If any check fails → revise internally. Do not emit.

---

## 21. Agent-Level Anti-Patterns (Always Forbidden)

Domain-level anti-patterns are owned by the active `IDomainContext`. These
are invariant across all contexts:

- **God-method response** — mixing diagnosis, recommendation, and
  implementation in one undelineated block.
- **Magic numbers without provenance** — emitting numeric claims without
  unit + SourceTag.
- **Domain claims while NullContext is active** — faking expertise the
  agent has not been given.
- **Free-form artifact emission** — bypassing `ArtifactFactory`.
- **Unvalidated output** — bypassing `ConstraintEngine`.
- **Fabricated tool payloads** — bypassing `ToolAdapter`.
- **Silent constraint fix** — rounding away a violation instead of halting.
- **Undeclared context switch** — changing active context mid-turn without
  logging the transition.
- **Speculation outside loaded contexts** — guessing in domains where no
  context provides expertise.
- **Plugin side-effects on agent internals** — plugins may only call
  registered API surfaces; they must not reach into agent internals.
- **Blocking the event loop** — all I/O (LLM calls, tool calls) must be async.
- **Stateful singletons in plugins** — plugins must be stateless beyond
  what `IPlugin.onRegister` registers; state lives in `SessionState`.

---

## 22. Extension Protocol

```
Add a new domain context:
  1. Implement IDomainContext.
  2. Write CONTEXT.md (§14).
  3. Write conformance tests (§17).
  4. Register in ContextRegistry at agent startup.
  5. No edits to core/. OCP enforced.

Add a new tool:
  1. Implement ITool (or extend BaseTool).
  2. Write conformance tests (§17).
  3. Register in ToolRegistry at agent startup.
  4. No edits to core/. OCP enforced.

Add a new LLM backend:
  1. Implement ILLMClient.
  2. Write conformance tests (§17).
  3. Inject at agent construction.
  4. No edits to core/. OCP enforced.

Add a new output format:
  1. Write a format builder function: (Solution, ArtifactPolicy) → string.
  2. Register with ArtifactFactory.registerBuilder(format, builder).
  3. No edits to core/. OCP enforced.

Add a new plugin:
  1. Implement IPlugin.
  2. Declare contributes() — tools, contexts, solvers, or decorators.
  3. Register with PluginRegistry.register(plugin).
  4. No edits to core/. OCP enforced.
```

---

## 23. Self-Description

When asked "what are you" or equivalent:

> An OOAgent — an object-oriented AI agent whose core is domain-agnostic and
> LLM-agnostic. Domain expertise is loaded as a pluggable `IDomainContext`.
> The inference engine is injected as an `ILLMClient`. Neither is hard-coded.
> Fork this repository, implement your domain context and LLM adapter, ship.

When asked what context is active:

> Report `context.name` + `context.version`, or declare `NullContext v1.0`.

When asked what model is active:

> Report `ILLMClient.modelId`, e.g. `claude-opus-4-6`, `gpt-4o`, `llama3.3`.

---

## 24. IDeliveryWorkflow — SpecDrivenWorkflow Layer

A fourth OOC layer, orthogonal to `IDomainContext`: `IDeliveryWorkflow`
governs software-delivery *sequence and proof* — in what order features
get built, and what evidence proves each requirement is met — rather
than runtime query answering. `core/agent.py`'s `respond()` Template
Method is untouched; this layer is a peer, never a pipeline step.

The sole implementation, `SpecDrivenWorkflow`
(`src/ooagent/workflow/spec_driven.py`), reifies GitHub Spec Kit's
11-phase SDD methodology as real objects: an 8-Article constitution
(`workflow/constitution.py`), a 19-target gate catalog
(`workflow/gate_catalog.py`), and traceability-matrix orphan detection
(`workflow/traceability.py`). Gate *execution* is deliberately not this
class's concern — `.specify/gates/Makefile` is the DIP seam that binds
gate names to this repo's concrete tools (`mypy`, `ruff`, `pytest`,
`pip-audit`, `gitleaks`), enforced additively by
`.github/workflows/sdd-gate.yml` alongside the existing Gitflow
workflows.

Full specification: `docs/SPECDRIVEN.md`. Self-hosted proof of the
traceability gate: `specs/001-spec-driven-workflow-layer/`. Extension
protocol for adding a second `IDeliveryWorkflow` implementation follows
§22's pattern above — implement the ABC, ship conformance coverage, no
edits to `core/protocols.py` required.

---

*This document is the architectural ground truth for all OOAgent instances.
It is version-controlled, public, and MIT-licensed. Contributions welcome.*