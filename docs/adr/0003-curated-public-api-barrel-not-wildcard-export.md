# ADR-0003: `ooagent`'s top-level barrel export is a curated list, not a wildcard re-export

## Status

Accepted

## Context

By the time this decision was made, the API-surface gap was narrower
than the original proposal assumed: every `ooagent` sub-package already
shipped its own `__all__` barrel export, and `ooagent.core.__init__`
already re-exported everything from `core/protocols.py` (via `from
ooagent.core.protocols import *` plus explicit imports), so `from
ooagent.core import OOAgent, Query, AgentConfig` already worked. The
only missing piece was `src/ooagent/__init__.py` itself — a bare
docstring with zero exports, so the literal `from ooagent import
OOAgent` ergonomic simply didn't exist. The underlying goal was broader
than fixing that one import, though: document which names are the
stable "core" surface versus the "advanced" surface reachable via
submodules, so the core-vs-advanced distinction is structural (import
depth signals tier) rather than just prose in a design doc.

## Decision

`ooagent/__init__.py` exports exactly 17 names, each a direct import
from its canonical module — no wildcard (`OOAgent`; `AgentConfig`,
`Query`, `Artifact`; `ILLMClient`, `IDomainContext`, `ITool`, `IPlugin`;
`ContextRegistry`, `ToolRegistry`; `OOAgentError` and its 6 concrete
exception subclasses) — documented in full in `docs/PUBLIC_API.md`'s
"Core primitives" table. The selection rule: everything the four
golden-path examples (`examples/*.py`) already import directly, plus
the exception hierarchy (needed to catch errors without deep imports),
minus anything that's an extension-authoring concern rather than an
app-building one. Names deliberately left in the advanced tier —
`PluginRegistry`, `ArtifactFactory`, `ConstraintEngine`,
`ResponsePipeline`, `LifecycleManager`, `MultiAgentOrchestrator`,
`SignalBus`, `ProvenanceTracker`, `ResponseDecorator`, `SessionState`,
`CircuitBreaker`, every ABC-only advanced interface, and
`IDeliveryWorkflow`/`SpecDrivenWorkflow` (a peer layer per CLAUDE.md
§24, not core, per ADR-0002) — stay reachable only via `ooagent.core`,
`ooagent.adapters.*`, `ooagent.contexts`, `ooagent.plugins.*`,
`ooagent.telemetry`, or `ooagent.workflow`.

## Consequences

The core-primitives list carries a real stability promise (CLAUDE.md
§18: a breaking change to any of the 17 names requires a major version
bump), while the advanced surface can be reorganized across minor
versions without a deprecation cycle, since it's implementation-adjacent
rather than the primary integration surface. New application authors
get an unambiguous, small starting import list (`from ooagent import
OOAgent, AgentConfig, Query, ...`) instead of needing to already know
the package layout. The cost is that this curated list must be manually
maintained — a new core-tier addition means an explicit edit to
`ooagent/__init__.py`'s list plus `docs/PUBLIC_API.md`'s table, not an
automatic pickup the way a wildcard export would provide.
