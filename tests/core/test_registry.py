"""tests/core/test_registry.py — ContextRegistry, ToolRegistry, PluginRegistry."""

from __future__ import annotations

import pytest

from ooagent.core.protocols import (
    ArtifactPolicy,
    IDomainContext,
    IPlugin,
    ITool,
    PluginContributions,
    ProblemClass,
    Query,
    Term,
)
from ooagent.core.registry import ContextRegistry, PluginRegistry, ToolRegistry


@pytest.fixture(autouse=True)
def _reset_context_registry_singleton():
    ContextRegistry.reset()
    yield
    ContextRegistry.reset()


class _FakeContext(IDomainContext):
    def __init__(self, name: str, version: str, keyword: str) -> None:
        self._name = name
        self._version = version
        self._keyword = keyword

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    def vocabulary(self):
        return {Term(label=self._keyword, definition="x", canonical=True)}

    def problem_classes(self):
        return set()

    def solvers(self):
        return {}

    def invariants(self):
        return []

    def pipeline(self):
        return []

    def anti_patterns(self):
        return []

    def required_inputs(self, pc: ProblemClass):
        return []

    def artifact_preferences(self) -> ArtifactPolicy:
        return ArtifactPolicy(preferred_formats=["text"], type_hints_required=False, comment_policy="none")

    def system_prompt_extension(self) -> str:
        return f"{self._name} active"

    def resolve_intent(self, query: Query):
        return None


def test_resolve_falls_back_to_null_context_when_no_match() -> None:
    registry = ContextRegistry.get_instance()
    result = registry.resolve(Query(text="totally unrelated query"))
    assert result.name == "NullContext"


def test_resolve_picks_highest_scoring_context() -> None:
    registry = ContextRegistry.get_instance()
    registry.register(_FakeContext("Engineering", "1.0", "torque"))
    registry.register(_FakeContext("Finance", "1.0", "invoice"))
    result = registry.resolve(Query(text="calculate the torque on this bolt"))
    assert result.name == "Engineering"


def test_tool_registry_register_get_all_has() -> None:
    class _FakeTool(ITool):
        @property
        def name(self):
            return "echo"

        @property
        def description(self):
            return "echoes input"

        def input_schema(self):
            return {}

        async def execute(self, args):
            return args

        def to_vendor_spec(self, vendor):
            return {}

    registry = ToolRegistry()
    tool = _FakeTool()
    registry.register(tool)
    assert registry.has("echo")
    assert registry.get("echo") is tool
    assert registry.all() == [tool]


def test_plugin_registry_rejects_duplicate_registration() -> None:
    class _FakePlugin(IPlugin):
        @property
        def plugin_id(self):
            return "test"

        @property
        def version(self):
            return "1.0"

        def on_register(self, agent):
            return None

        def on_dispose(self):
            return None

        def contributes(self):
            return PluginContributions()

    registry = PluginRegistry()
    registry.register(_FakePlugin())
    with pytest.raises(ValueError):
        registry.register(_FakePlugin())
