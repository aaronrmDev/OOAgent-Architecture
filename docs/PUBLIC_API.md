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
| `ITool` | Implement this (or extend `BaseTool`, `ooagent.adapters.tools.base`) to add a new tool. |
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
describes. `ooagent.mcp` (the MCP server, [`docs/MCP.md`](MCP.md)) is a
further step removed — it's an optional extra (`pip install
ooagent[mcp]`), not installed by default, since most consumers of the
core library have no need for it.
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
