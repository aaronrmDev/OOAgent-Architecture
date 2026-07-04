"""plugins/scope_guard/__init__.py — ScopeGuardPlugin.

Contributes an IDomainContext that injects a pipeline step enforcing domain
boundaries. The step blocks queries that match explicit out-of-scope
patterns, emitting a ScopeExitError before the SOLVING phase — protecting
both cost and quality.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ooagent.core.protocols import (
    AntiPattern,
    ArtifactPolicy,
    IDomainContext,
    InputSpec,
    ISolver,
    Invariant,
    PipelineStep,
    PipelineStepResult,
    PluginContributions,
    ProblemClass,
    Query,
    ScopeExitError,
    Term,
)
from ooagent.plugins.base_plugin import AbstractPlugin


@dataclass(frozen=True)
class ScopeGuardOptions:
    """`blocked_patterns`: keyword patterns (lowercase) that trigger a scope
    exit. If the query text contains any of these, the turn is halted.
    `context_name`: name of the guard context reported in error artifacts.
    Default: 'ScopeGuard'."""

    blocked_patterns: list[str] = field(default_factory=list)
    context_name: str = "ScopeGuard"


class _ScopeGuardStep:
    """Structural PipelineStep (duck-typed) — blocks queries matching blocked patterns."""

    name = "scope-guard"

    def __init__(self, context_name: str, blocked: list[str]) -> None:
        self._context_name = context_name
        self._blocked = blocked

    async def run(self, query: Query, _ctx: IDomainContext) -> PipelineStepResult:
        text = query.text.lower()
        hit = next((p for p in self._blocked if p in text), None)
        if hit is not None:
            raise ScopeExitError(self._context_name, query.text)
        return PipelineStepResult(passed=True, extras={})


class ScopeGuardContext(IDomainContext):
    """A context that contributes only the scope-guard pipeline step."""

    version = "1.0.0"

    def __init__(self, name: str, blocked: list[str]) -> None:
        self._name = name
        self._blocked = [p.lower() for p in blocked]

    @property
    def name(self) -> str:
        return self._name

    def vocabulary(self) -> set[Term]:
        return set()

    def problem_classes(self) -> set[ProblemClass]:
        return set()

    def solvers(self) -> dict[str, ISolver]:
        return {}

    def invariants(self) -> list[Invariant]:
        return []

    def anti_patterns(self) -> list[AntiPattern]:
        return []

    def required_inputs(self, pc: ProblemClass) -> list[InputSpec]:
        return []

    def resolve_intent(self, query: Query) -> ProblemClass | None:
        return None

    def artifact_preferences(self) -> ArtifactPolicy:
        return ArtifactPolicy(
            preferred_formats=["text"], type_hints_required=False, comment_policy="none"
        )

    def system_prompt_extension(self) -> str:
        return (
            "ScopeGuard is active. The following topics are out of scope: "
            f"{', '.join(self._blocked)}."
        )

    def pipeline(self) -> list[PipelineStep]:
        return [_ScopeGuardStep(self._name, self._blocked)]


class ScopeGuardPlugin(AbstractPlugin):
    plugin_id = "ooagent.scope-guard"
    version = "1.0.0"

    def __init__(self, opts: ScopeGuardOptions | None = None) -> None:
        opts = opts or ScopeGuardOptions()
        self._context = ScopeGuardContext(opts.context_name, opts.blocked_patterns)

    def on_dispose(self) -> None:
        return None

    def contributes(self) -> PluginContributions:
        return PluginContributions(contexts=[self._context])

    @property
    def guard_context(self) -> IDomainContext:
        """The underlying guard context — useful for direct inspection in tests."""
        return self._context
