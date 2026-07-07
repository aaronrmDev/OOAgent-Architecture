# Public API & Stability Contract — Design

## Purpose

Sub-project B of the OOAgent improvement backlog (see
`docs/superpowers/specs/2026-07-06-golden-path-examples-design.md`'s
decomposition table). The original proposal asked for a "cleaner
top-level import story" (`from ooagent import OOAgent`) and a
public/internal API stability statement. Investigation during
brainstorming found the actual gap is narrow: every sub-package already
has a proper `__all__` barrel export, and `ooagent.core.__init__`
already re-exports everything via `from ooagent.core.protocols import *`
plus explicit imports — so `from ooagent.core import OOAgent, Query,
AgentConfig` already works today. The one missing piece is
`src/ooagent/__init__.py` itself, which is a bare docstring with zero
exports, so the literal `from ooagent import OOAgent` ergonomic doesn't
work — not because of a deep API-surface problem, just a missing file.

**Goal:** make `from ooagent import OOAgent` (and a curated set of other
core primitives) work, and document which names are the stable "core"
surface versus the "advanced" surface reachable via submodules — turning
the proposal's "distinguish core primitives from advanced extension
points" recommendation into something structural (import depth signals
tier), not just prose.

## Scope

**In scope:**

1. `src/ooagent/__init__.py` — a curated re-export of the "core
   primitives" tier (list below).
2. `tests/test_public_api.py` — one test asserting every top-level name
   is importable and is the *same object* (`is`, not just equal) as its
   canonical submodule location — catches accidental duplication or a
   future refactor silently breaking the top-level surface.
3. `docs/PUBLIC_API.md` — the core-vs-advanced table, a one-line
   decision guide, and a reference (not restatement) of CLAUDE.md §18's
   existing per-component versioning strategy.
4. One new line in `README.md`'s existing "Go Deeper" list (added in
   sub-project A), linking to `docs/PUBLIC_API.md`.

**Out of scope** (per brainstorming discussion):

- Changing the CalVer (`YYYY.MM.NN`) versioning scheme to SemVer —
  CLAUDE.md §18 already documents CalVer as an intentional, per-component
  strategy; changing it would touch `scripts/version-check.sh` and CI for
  marginal benefit given no evidence the current scheme causes real
  friction.
- Adding new fields to `AgentConfig` — it already covers retries,
  timeouts, and the circuit-breaker threshold; the proposal's suggested
  additions (temperature, tool policy, validation policy) are
  per-request or plugin-level concerns (`CompletionRequest.temperature`,
  `ScopeGuardPlugin`, `SecurityPlugin`), not agent-construction config.

## The core-primitives export list

`src/ooagent/__init__.py` re-exports exactly these names, each a direct
import from its canonical module (no wildcard):

```
OOAgent                                          (core.agent)
AgentConfig, Query, Artifact                     (core.protocols)
ILLMClient, IDomainContext, ITool, IPlugin        (core.protocols — the 4 extension points)
ContextRegistry, ToolRegistry                    (core.registry)
OOAgentError, ConstraintViolationError,
FSMViolationError, LifecycleError,
ToolExecutionError, TokenLimitError,
ScopeExitError                                    (core.protocols — the exception hierarchy)
```

Selection rule: everything the four golden-path examples
(`examples/*.py`, sub-project A) already import directly, plus the
exception hierarchy (needed to catch errors without deep imports),
minus anything that's an extension-authoring concern rather than an
app-building one.

**Deliberately not promoted** (stays reachable only via `ooagent.core`
or its own submodule — the "advanced" tier): `PluginRegistry`,
`ArtifactFactory`, `ConstraintEngine`, `ResponsePipeline`,
`LifecycleManager`, `MultiAgentOrchestrator`, `SignalBus`,
`ProvenanceTracker`, `ResponseDecorator`, `SessionState`,
`CircuitBreaker`, every ABC-only advanced interface (`ISolver`,
`ILifecycle`, `ISessionState`, `ITelemetryProvider`, `IArtifactFactory`,
`IOrchestrator`, `IContextHost`, `IConversationalObject`, `IToolUser`,
`IObservable`, `IVisitor`, `IArtifactNode`, `IPrototypable`), and
`IDeliveryWorkflow`/`SpecDrivenWorkflow` (a peer layer per CLAUDE.md §24,
not core).

## `docs/PUBLIC_API.md` structure

```markdown
# Public API & Stability

## Core primitives (`from ooagent import ...`)
[table: name | what it's for]

## Advanced surface (`from ooagent.core import ...` / submodules)
[table: name | module | when you need it]

## Stability contract
[one paragraph + link to CLAUDE.md §18 — core primitives follow the
same semver-stable rule §18 already states for core/protocols.py;
advanced-tier names may shift module location across minor versions
without a deprecation cycle, since they're implementation-adjacent]

## Deciding which tier you need
- Building an app on OOAgent → core primitives are almost always enough.
- Extending the framework (new adapter/tool/plugin/context) → you'll
  also need the submodule imports documented in CLAUDE.md §22's
  extension protocol.
```

## Testing

`tests/test_public_api.py`:

```python
def test_ooagent_is_the_same_object_as_core_agent_ooagent():
    from ooagent import OOAgent as top_level
    from ooagent.core.agent import OOAgent as canonical
    assert top_level is canonical
```

...one such identity assertion per exported name (14 total), grouped by
source module. Non-vacuous: this would fail if a future edit
accidentally re-defines rather than re-imports a name at the top level.

## Out-of-scope confirmation

No changes to any submodule's existing `__all__` lists, `AgentConfig`'s
fields, or `pyproject.toml`'s version scheme. `core/agent.py`'s
`respond()` and all other runtime behavior are untouched — this is a
purely additive import-surface and documentation change.
