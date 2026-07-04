"""tests/core/test_orchestrator.py — MultiAgentOrchestrator, SignalBus."""

from __future__ import annotations

from ooagent.core.orchestrator import MultiAgentOrchestrator, SignalBus
from ooagent.core.protocols import ArtifactPolicy, IDomainContext, ProblemClass, Query


class _StubContext(IDomainContext):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "1.0"

    def vocabulary(self):
        return set()

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
        return ArtifactPolicy(
            preferred_formats=["text"], type_hints_required=False, comment_policy="none"
        )

    def system_prompt_extension(self) -> str:
        return f"{self._name} active"

    def resolve_intent(self, query: Query):
        return None


class _EchoAgent:
    def __init__(self, name: str) -> None:
        self._name = name

    async def respond(self, query: Query) -> str:
        return f"{self._name}: {query.text}"


def test_signal_bus_publish_subscribe_and_unsubscribe() -> None:
    bus = SignalBus()
    received = []
    unsubscribe = bus.subscribe("done", lambda payload: received.append(payload))
    bus.publish("done", {"x": 1})
    assert received == [{"x": 1}]
    unsubscribe()
    bus.publish("done", {"x": 2})
    assert received == [{"x": 1}]


async def test_dispatch_runs_all_specialists_and_publishes_signal() -> None:
    orchestrator = MultiAgentOrchestrator(lambda ctx: _EchoAgent(ctx.name))
    events = []
    orchestrator.bus.subscribe("specialist.done", lambda payload: events.append(payload))
    solutions = await orchestrator.dispatch(
        Query(text="hello"), [_StubContext("Engineering"), _StubContext("Finance")]
    )
    assert len(solutions) == 2
    assert {s.content for s in solutions} == {"Engineering: hello", "Finance: hello"}
    assert len(events) == 2


async def test_synthesize_concatenates_solution_content() -> None:
    orchestrator = MultiAgentOrchestrator(lambda ctx: _EchoAgent(ctx.name))
    solutions = await orchestrator.dispatch(Query(text="hi"), [_StubContext("A")])
    result = await orchestrator.synthesize(solutions, Query(text="hi"))
    assert result.content == "A: hi"


async def test_dispatch_captures_specialist_errors_as_solution() -> None:
    class _FailingAgent:
        async def respond(self, query: Query) -> str:
            raise RuntimeError("boom")

    orchestrator = MultiAgentOrchestrator(lambda ctx: _FailingAgent())
    solutions = await orchestrator.dispatch(Query(text="hi"), [_StubContext("Broken")])
    assert "[SpecialistError] Broken" in solutions[0].content
