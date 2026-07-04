"""contexts/null_context.py — NullContext (Null Object pattern).

Answers safely when no domain is loaded — §4 GoF, §9 CLAUDE.md
"""

from __future__ import annotations

from ooagent.core.protocols import (
    AntiPattern,
    ArtifactPolicy,
    IDomainContext,
    InputSpec,
    Invariant,
    ISolver,
    PipelineStep,
    ProblemClass,
    Query,
    Term,
)


class NullContext(IDomainContext):
    @property
    def name(self) -> str:
        return "NullContext"

    @property
    def version(self) -> str:
        return "1.0"

    def vocabulary(self) -> set[Term]:
        return set()

    def problem_classes(self) -> set[ProblemClass]:
        return set()

    def solvers(self) -> dict[str, ISolver]:
        return {}

    def invariants(self) -> list[Invariant]:
        return []

    def pipeline(self) -> list[PipelineStep]:
        return []

    def anti_patterns(self) -> list[AntiPattern]:
        return []

    def required_inputs(self, pc: ProblemClass) -> list[InputSpec]:
        return []

    def artifact_preferences(self) -> ArtifactPolicy:
        return ArtifactPolicy(
            preferred_formats=["text"],
            type_hints_required=False,
            comment_policy="none",
        )

    def system_prompt_extension(self) -> str:
        return (
            "NullContext v1.0 is active. No domain context has been loaded. "
            "Do not make domain-specific claims. "
            "If the user asks domain questions, state which context is active "
            "and what is unavailable."
        )

    def resolve_intent(self, query: Query) -> ProblemClass | None:
        return None
