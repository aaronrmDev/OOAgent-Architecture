# ADR-0001: OOAgent is a composition root, not a class hierarchy

## Status

Accepted

## Context

An AI agent framework needs to combine many independent concerns per
turn: LLM backend selection, domain-context resolution, tool execution,
plugin extension points, session/FSM state, response validation,
artifact building, and telemetry. A natural first instinct is to model
this as a deep inheritance hierarchy — a base `Agent` class, subclassed
per capability (`ToolUsingAgent`, `ContextAwareAgent`,
`ObservableAgent`, ...) — but multiple inheritance or deep single
inheritance chains make it hard to add a new capability (a new LLM
vendor, a new domain, a new plugin) without touching or subclassing
existing code, violating the Open/Closed Principle.

## Decision

`OOAgent` (`src/ooagent/core/agent.py`) is a **composition root**: it
composes, via constructor injection, an `ILLMClient`, a
`ContextRegistry`, a `ToolRegistry`, a `PluginRegistry`, a
`SessionState`, a `LifecycleManager`, a `ResponsePipeline`, a
`SolverDispatcher`, an `ArtifactFactory`, a `ConstraintEngine`, a
`ProvenanceTracker`, a `TelemetryProvider`, and a `ResponseDecorator` —
each collaborator owning exactly one concern (CLAUDE.md §1). The class
hierarchy above `OOAgent` (`IAgent` → `AbstractAgent` → `LLMAgent` →
`OOAgent`) is shallow and exists only to layer in the minimal state each
level actually needs (an `agent_id`, then an `ILLMClient` reference) —
not to carry behavior via subclassing. Extension happens by injecting a
new implementation of an interface (a new `ILLMClient`, a new
`IDomainContext`, a new `ITool`, a new `IPlugin`), never by subclassing
`OOAgent` itself except to override a single protected Template Method
step (CLAUDE.md §8a).

## Consequences

Adding a new LLM vendor, domain, tool, or plugin requires zero edits to
`core/` — each is a new class implementing an existing interface,
registered at construction time (CLAUDE.md §22's Extension Protocol).
Testing is straightforward: any collaborator can be replaced with a test
double independently (`StubLLMClient`, `NullContext`, `NullTelemetry`).
The cost is more constructor parameters on `OOAgent.__init__` as new
collaborators are added, and a discipline requirement — no collaborator
may reach into another's internals (CLAUDE.md §21's "Plugin side-effects
on agent internals" anti-pattern) — that has to be enforced by review
and interface design (`IPlugin` accepting only `IAgent`, not `OOAgent`),
not by the type system alone.
