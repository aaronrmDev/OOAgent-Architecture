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
language (Python, TypeScript, Go, Rust, Java, C#, etc.).

```typescript
// ── Generics notation (TypeScript-style pseudocode) ─────────────────────────

interface IAgent<TQuery, TResponse> {
  respond(query: TQuery): Promise<TResponse>
  readonly agentId: string
  readonly state:   ISessionState
}

interface ILLMClient {
  complete(request: CompletionRequest): Promise<CompletionResponse>
  stream(request: CompletionRequest):   AsyncIterator<CompletionChunk>
  readonly modelId:    string
  readonly maxTokens:  number
  readonly supportsTools: boolean
}

interface IDomainContext {
  readonly name:    string
  readonly version: string
  vocabulary():         Set<Term>
  problemClasses():     Set<ProblemClass>
  solvers():            Map<string, ISolver>
  invariants():         Invariant[]
  pipeline():           PipelineStep[]
  antiPatterns():       AntiPattern[]
  requiredInputs(pc: ProblemClass): InputSpec[]
  artifactPreferences(): ArtifactPolicy
  systemPromptExtension(): string
  resolveIntent(query: Query): ProblemClass | null
}

interface ISolver {
  canSolve(problemClass: string): boolean
  solve(query: Query, ctx: IDomainContext): Promise<Solution>
}

interface ITool {
  readonly name:        string
  readonly description: string
  inputSchema():        JSONSchema
  execute(args: Record<string, unknown>): Promise<unknown>
  toVendorSpec(vendor: LLMVendor): VendorToolSpec
}

interface IPlugin {
  readonly pluginId:   string
  readonly version:    string
  onRegister(agent: IAgent<unknown, unknown>): void
  onDispose():         void
  contributes(): PluginContributions   // tools | contexts | solvers | decorators
}

interface ILifecycle {
  initialize(config: IAgentConfig): Promise<void>
  healthCheck():      Promise<HealthStatus>
  dispose():          Promise<void>         // releases all managed resources
  readonly isReady:   boolean
}

interface ISessionState {
  readonly fsm:           AgentFSMState
  readonly turn:          number
  readonly contextName:   string
  transition(to: AgentFSMState): void
  snapshot():             Memento
  restore(id: string):    void
  commit(cmd: Command):   void
  subscribe(obs: StateObserver): Unsubscribe
}

interface ITelemetryProvider {
  span<T>(name: string, fn: () => Promise<T>): Promise<T>
  counter(name: string, delta?: number): void
  gauge(name: string, value: number): void
  histogram(name: string, value: number): void
  event(name: string, payload: Record<string, unknown>): void
}

interface IArtifactFactory {
  build(solution: Solution, format: ArtifactFormat, policy: ArtifactPolicy): Artifact
  buildError(violation: string, ctx: string): Artifact
  buildMissingInputs(missing: InputSpec[], ctx: string): Artifact
  buildScopeExit(ctx: string, query: string): Artifact
}

interface IOrchestrator {
  dispatch(query: Query, contexts: IDomainContext[]): Promise<Solution[]>
  synthesize(solutions: Solution[], original: Query): Promise<Solution>
}
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
ooagent/
├── core/
│   ├── protocols.ts          # All interface + type definitions (zero dependencies)
│   ├── agent.ts              # OOAgent — composition root, Template Method
│   ├── state.ts              # SessionState, FSM, Memento, Command
│   ├── pipeline.ts           # ResponsePipeline (CoR), ConstraintEngine
│   ├── artifacts.ts          # ArtifactFactory, ProvenanceTracker, ResponseDecorator
│   ├── registry.ts           # ContextRegistry, ToolRegistry, PluginRegistry
│   ├── lifecycle.ts          # LifecycleManager, HealthStatus, CircuitBreaker
│   └── orchestrator.ts       # MultiAgentOrchestrator, SignalBus
│
├── adapters/
│   ├── llm/
│   │   ├── anthropic.ts      # ILLMClient → Anthropic SDK
│   │   ├── openai.ts         # ILLMClient → OpenAI SDK
│   │   ├── gemini.ts         # ILLMClient → Gemini SDK
│   │   ├── ollama.ts         # ILLMClient → Ollama (local)
│   │   └── caching_proxy.ts  # CachingLLMProxy (Proxy pattern)
│   └── tools/
│       ├── base.ts           # BaseTool abstract class
│       └── adapter.ts        # ToolAdapter (Adapter pattern)
│
├── contexts/
│   ├── null_context.ts       # NullContext (Null Object)
│   └── [domain]/             # User-supplied IDomainContext implementations
│       └── CONTEXT.md        # Domain specification (see §14)
│
├── plugins/
│   ├── registry.ts           # PluginRegistry
│   └── [plugin-name]/        # User-supplied IPlugin implementations
│
├── telemetry/
│   ├── null_telemetry.ts     # NullTelemetry (Null Object — default)
│   ├── otel.ts               # OpenTelemetry IITelemetryProvider
│   └── console.ts            # ConsoleTelemery (development)
│
└── testing/
    ├── stub_llm_client.ts    # Deterministic ILLMClient for unit tests
    ├── null_context.ts       # Re-exports NullContext
    └── fixtures.ts           # Common Query/Solution/Artifact test doubles
```

**Package management rules:**
- `core/protocols.ts` has **zero runtime dependencies** — only type imports.
- `core/` depends only on `core/protocols.ts`. No adapter, no context, no plugin.
- `adapters/` depends on `core/` and external SDKs — never on `contexts/` or `plugins/`.
- `contexts/` depends on `core/protocols.ts` only.
- `plugins/` depends on `core/protocols.ts` + any `adapters/` they need.
- Circular imports are a build error (`eslint-plugin-import`, `ruff`, etc.).
- Every package exports a single barrel (`index.ts`) with explicit re-exports.
- Versioning: `core/` is semver-stable. Breaking changes to `IAgent`, `IDomainContext`,
  or `ILLMClient` require a major version bump.

---

## 8. Inheritance & Specialization Guide

### 8a. Specializing the Agent

```typescript
// Extend OOAgent only to override a single Template Method step.
// Never override respond() directly.

class StreamingAgent extends OOAgent {
  // Override only the solve step to use streaming
  protected override async _solve(q, ctx, extras): Promise<Solution> {
    // use ILLMClient.stream() instead of .complete()
  }
}

class CachedAgent extends OOAgent {
  // Inject a CachingLLMProxy at construction — no subclassing needed
  // Prefer composition (Proxy) over inheritance for cross-cutting concerns.
}

class EmbeddedAgent extends OOAgent<EmbeddedQuery, EmbeddedResponse> {
  // Narrow the generics for a specialized query/response type
}
```

**Rule:** prefer composition + injection over inheritance. Subclass only when
you need to override a protected Template Method step. Every subclass must
satisfy LSP: same preconditions, same postconditions, same invariants.

### 8b. Specializing the Context

```typescript
class MyDomainContext implements IDomainContext {
  name    = "MyDomain"
  version = "1.0"
  // Implement all 10 methods.
  // Ship this in contexts/my-domain/ with a CONTEXT.md.
}
```

**Rule:** contexts are **closed for modification, open for composition**.
If two domains partially overlap, compose them:

```typescript
class HybridContext implements IDomainContext {
  constructor(
    private readonly a: IDomainContext,
    private readonly b: IDomainContext,
  ) {}

  vocabulary() { return new Set([...this.a.vocabulary(), ...this.b.vocabulary()]) }
  invariants() { return [...this.a.invariants(), ...this.b.invariants()] }
  // etc. — merge, not override
}
```

### 8c. Specializing Tools

```typescript
class MyTool implements ITool {
  name        = "my_tool"
  description = "..."

  inputSchema(): JSONSchema { return { ... } }

  async execute(args): Promise<unknown> {
    // Validate args against inputSchema() before executing — always.
    // Throw ToolExecutionError on failure — never return error strings.
    // Be idempotent where possible.
  }

  toVendorSpec(vendor: LLMVendor): VendorToolSpec {
    // Return the vendor-specific tool spec.
    // BaseTool provides default implementations for known vendors.
  }
}
```

### 8d. Plugin Contributions

```typescript
class MyPlugin implements IPlugin {
  pluginId = "my-plugin"
  version  = "1.0.0"

  onRegister(agent) {
    // Register tools, contexts, solvers, or decorators here.
    // Never hold a strong reference to agent — use WeakRef if needed.
  }

  onDispose() {
    // Release all resources this plugin allocated.
    // Must be idempotent — may be called multiple times.
  }

  contributes(): PluginContributions {
    return {
      tools:    [new MyTool()],
      contexts: [new MyDomainContext()],
    }
  }
}
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

```typescript
async respond(query: Query): Promise<Response> {
  // Pre-condition: isReady === true
  // Post-condition: returns non-null Response; SessionState.turn incremented

  this.provenance.clear()
  this.state.transition(FSM.GATHERING)

  const context  = this.ctxRegistry.resolve(query)           // IDomainContext
  this.state.setContext(context.name)
  const pipeline = this.pipeline.extend(context.pipeline())  // CoR
  const snapshot = this.state.snapshot()                     // Memento

  // MODELING: validate query
  this.state.transition(FSM.MODELING)
  const extras = await pipeline.run(query, context)
  // ConstraintViolation → FSM.FAILURE → emit error artifact → return

  // SOLVING: LLM + tool loop
  this.state.transition(FSM.SOLVING)
  const solution = await this.solve(query, context, extras)
  // ScopeExitError  → FSM.FAILURE → emit scope-exit artifact → return

  // VALIDATING: domain invariants
  this.state.transition(FSM.VALIDATING)
  this.constraintEngine.assertAll(solution, context.invariants())
  // ConstraintViolation → FSM.FAILURE → emit violation artifact → return

  // DELIVERING: build + decorate artifact
  this.state.transition(FSM.DELIVERING)
  const artifact = this.artifactFactory.build(solution, format, context.artifactPreferences())
  const enriched = this.decorator.apply(artifact, this.provenance.dump())

  this.state.commit(Command.fromTurn(query, solution, context.name, this.state.trace))
  this.state.reset()                                         // → FSM.IDLE

  this.telemetry.event("turn.complete", { context: context.name, format, tokens: ... })
  return enriched
  // Invariants: FSM === IDLE; turn incremented by 1; provenance cleared
}
```

**No step is skipped. No emission occurs without `assertAll` passing.**

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

*This document is the architectural ground truth for all OOAgent instances.
It is version-controlled, public, and MIT-licensed. Contributions welcome.*