"""tests/test_null_context.py — NullContext (Null Object)."""

from __future__ import annotations

from ooagent.contexts.null_context import NullContext
from ooagent.core.protocols import Query


def test_null_context_reports_empty_vocabulary_and_problem_classes() -> None:
    ctx = NullContext()
    assert ctx.name == "NullContext"
    assert ctx.version == "1.0"
    assert ctx.vocabulary() == set()
    assert ctx.problem_classes() == set()
    assert ctx.solvers() == {}
    assert ctx.invariants() == []
    assert ctx.pipeline() == []


def test_null_context_resolve_intent_always_returns_none() -> None:
    ctx = NullContext()
    assert ctx.resolve_intent(Query(text="anything")) is None


def test_null_context_artifact_preferences_default_to_text() -> None:
    ctx = NullContext()
    prefs = ctx.artifact_preferences()
    assert prefs.preferred_formats == ["text"]
    assert prefs.type_hints_required is False


def test_null_context_system_prompt_extension_declares_itself() -> None:
    ctx = NullContext()
    assert "NullContext" in ctx.system_prompt_extension()
