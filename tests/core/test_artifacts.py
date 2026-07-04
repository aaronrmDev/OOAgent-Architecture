"""tests/core/test_artifacts.py — ArtifactFactory, ProvenanceTracker, ResponseDecorator."""

from __future__ import annotations

from ooagent.core.artifacts import ArtifactFactory, ProvenanceTracker, ResponseDecorator
from ooagent.core.protocols import ArtifactPolicy, Solution, SourceRecord


def test_build_uses_registered_builder_when_present() -> None:
    factory = ArtifactFactory()
    factory.register_builder("md", lambda solution, policy: f"# {solution.content}")
    solution = Solution(
        content="Title", format="md", sources=[SourceRecord(tag="derived", ref="calc")]
    )
    policy = ArtifactPolicy(
        preferred_formats=["md"], type_hints_required=False, comment_policy="none"
    )
    artifact = factory.build(solution, "md", policy)
    assert artifact.content == "# Title"
    assert artifact.provenance[0].source == "calc"
    assert artifact.provenance[0].tag == "derived"


def test_build_falls_back_to_solution_content_without_builder() -> None:
    factory = ArtifactFactory()
    solution = Solution(content="raw text", format="text", sources=[])
    policy = ArtifactPolicy(
        preferred_formats=["text"], type_hints_required=False, comment_policy="none"
    )
    artifact = factory.build(solution, "text", policy)
    assert artifact.content == "raw text"


def test_build_error_includes_context_and_violation() -> None:
    factory = ArtifactFactory()
    artifact = factory.build_error("bad value", "Engineering")
    assert "[ConstraintViolation]" in artifact.content
    assert "Engineering" in artifact.content
    assert "bad value" in artifact.content


def test_provenance_tracker_records_and_clears() -> None:
    tracker = ProvenanceTracker()
    tracker.record("wikipedia.org", "cited")
    assert len(tracker.dump()) == 1
    tracker.clear()
    assert tracker.dump() == []


def test_response_decorator_applies_all_decorators_in_order() -> None:
    from ooagent.core.protocols import Artifact

    decorator = ResponseDecorator()
    decorator.add_decorator(
        lambda artifact, prov: Artifact(
            content=artifact.content + " [1]",
            format=artifact.format,
            provenance=artifact.provenance,
        )
    )
    decorator.add_decorator(
        lambda artifact, prov: Artifact(
            content=artifact.content + " [2]",
            format=artifact.format,
            provenance=artifact.provenance,
        )
    )
    base = Artifact(content="base", format="text", provenance=[])
    result = decorator.apply(base, [])
    assert result.content == "base [1] [2]"
