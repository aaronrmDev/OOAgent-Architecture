"""tests/conformance/test_context.py — IDomainContext conformance suite (§17 CLAUDE.md)."""

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


class StubDomainContext(IDomainContext):
    """Minimal conformant IDomainContext for conformance testing."""

    @property
    def name(self) -> str:
        return "StubConformance"

    @property
    def version(self) -> str:
        return "1.0.0"

    def vocabulary(self) -> set[Term]:
        return {Term(label="stub-term", definition="A test term", canonical=True)}

    def problem_classes(self) -> set[ProblemClass]:
        return {ProblemClass(name="StubProblem", description="Stub problem class", solver="stub")}

    def solvers(self) -> dict[str, ISolver]:
        return {}

    def invariants(self) -> list[Invariant]:
        return [
            Invariant(
                name="stub-invariant",
                condition="true",
                severity="error",
                rationale="test",
            )
        ]

    def anti_patterns(self) -> list[AntiPattern]:
        return []

    def required_inputs(self, pc: ProblemClass) -> list[InputSpec]:
        return []

    def resolve_intent(self, query: Query) -> ProblemClass | None:
        return None

    def artifact_preferences(self) -> ArtifactPolicy:
        return ArtifactPolicy(
            preferred_formats=["text", "json"],
            type_hints_required=True,
            comment_policy="none",
        )

    def system_prompt_extension(self) -> str:
        return "Stub context active."

    def pipeline(self) -> list[PipelineStep]:
        return []


ctx: IDomainContext = StubDomainContext()
null_query = Query(text="", format="text", metadata={})


def test_vocabulary_returns_non_empty_set_of_terms() -> None:
    vocab = ctx.vocabulary()
    assert len(vocab) > 0, "vocabulary() must return a non-empty set"


def test_problem_classes_returns_non_empty_set_of_problem_class() -> None:
    classes = ctx.problem_classes()
    assert len(classes) > 0, "problem_classes() must return a non-empty set"


def test_invariants_are_callable_without_throwing() -> None:
    result = ctx.invariants()
    assert isinstance(result, list), "invariants() must return a list"


def test_resolve_intent_returns_none_for_unrecognized_query() -> None:
    result = ctx.resolve_intent(null_query)
    assert result is None, "resolve_intent must return None for unrecognized queries — not throw"


def test_artifact_preferences_preferred_formats_is_non_empty() -> None:
    prefs = ctx.artifact_preferences()
    assert len(prefs.preferred_formats) > 0, (
        "artifact_preferences().preferred_formats must be non-empty"
    )
