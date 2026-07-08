"""tests/core/test_agent.py — OOAgent end-to-end Template Method (respond())."""

from __future__ import annotations

import pytest

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import (
    AgentConfig,
    CompletionChunk,
    CompletionResponse,
    ILLMClient,
    ITelemetryProvider,
    LifecycleError,
    Query,
    TokenUsage,
)
from ooagent.core.registry import ContextRegistry


class _StubLLMClient(ILLMClient):
    async def complete(self, request):
        return CompletionResponse(
            content="hello world",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    async def stream(self, request):
        yield CompletionChunk(delta="hi", done=True)

    @property
    def model_id(self):
        return "stub-1"

    @property
    def vendor(self):
        return "anthropic"

    @property
    def max_tokens(self):
        return 4096

    @property
    def supports_tools(self):
        return False


@pytest.fixture(autouse=True)
def _reset_context_registry_singleton():
    ContextRegistry.reset()
    yield
    ContextRegistry.reset()


async def test_respond_before_initialize_raises_lifecycle_error() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    with pytest.raises(LifecycleError):
        await agent.respond(Query(text="hi"))


async def test_respond_runs_full_fsm_and_returns_artifact() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())
    artifact = await agent.respond(Query(text="hello agent"))
    assert artifact.content == "hello world"
    assert artifact.format == "text"
    assert agent.state.fsm == "IDLE"
    assert agent.state.turn == 1
    await agent.dispose()


async def test_dispose_is_idempotent_second_call_is_a_noop() -> None:
    # §17 CLAUDE.md's dispose-idempotency conformance requirement: calling
    # dispose() twice must not raise. The first call transitions the agent
    # to disposed; the second call is a no-op given that state.
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())
    await agent.dispose()
    await agent.dispose()  # must not raise
    assert not agent.is_ready


async def test_agent_id_is_generated_when_not_supplied() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    assert len(agent.agent_id) > 0


async def test_respond_recovers_when_artifact_factory_raises_during_delivering() -> None:
    # Bug 1 regression: an exception raised inside the DELIVERING block (e.g.
    # from a third-party ResponseDecorator — a legitimate OCP extension point)
    # must not leave the FSM stuck at DELIVERING, since DELIVERING's only
    # legal transition is to IDLE — a stuck FSM would brick every future
    # respond() call with FSMViolationError.
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())

    def _boom(artifact, provenance):
        raise RuntimeError("boom")

    agent._decorator.add_decorator(_boom)

    artifact = await agent.respond(Query(text="hello agent"))
    assert "boom" in artifact.content
    assert agent.state.fsm == "IDLE"

    # Second call must not raise FSMViolationError — the agent is not bricked.
    artifact2 = await agent.respond(Query(text="hello again"))
    assert "boom" in artifact2.content
    assert agent.state.fsm == "IDLE"

    await agent.dispose()


class _AlwaysFailingLLMClient(ILLMClient):
    async def complete(self, request):
        raise RuntimeError("llm down")

    async def stream(self, request):
        yield CompletionChunk(delta="", done=True)

    @property
    def model_id(self):
        return "stub-fail"

    @property
    def vendor(self):
        return "anthropic"

    @property
    def max_tokens(self):
        return 4096

    @property
    def supports_tools(self):
        return False


class _RecordingTelemetry(ITelemetryProvider):
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def span(self, name, fn):
        return await fn()

    def counter(self, name, delta=1):
        return None

    def gauge(self, name, value):
        return None

    def histogram(self, name, value):
        return None

    def event(self, name, payload):
        self.events.append((name, payload))


async def test_llm_call_events_fire_on_success() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_StubLLMClient(), telemetry=telemetry)
    await agent.initialize(AgentConfig())

    await agent.respond(Query(text="hello agent"))

    assert ("llm.call_started", {"round": 0, "vendor": "anthropic"}) in telemetry.events
    assert (
        "llm.call_completed",
        {"round": 0, "vendor": "anthropic", "input_tokens": 1, "output_tokens": 1},
    ) in telemetry.events

    await agent.dispose()


async def test_llm_call_failed_event_fires_on_llm_error() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_AlwaysFailingLLMClient(), telemetry=telemetry)
    await agent.initialize(AgentConfig())

    await agent.respond(Query(text="hello agent"))

    assert ("llm.call_started", {"round": 0, "vendor": "anthropic"}) in telemetry.events
    assert (
        "llm.call_failed",
        {"round": 0, "vendor": "anthropic", "error_type": "RuntimeError"},
    ) in telemetry.events

    await agent.dispose()


async def test_llm_failure_increments_circuit_breaker_by_exactly_one() -> None:
    # Bug 2 regression: _handle_failure() used to unconditionally call
    # record_llm_failure() in addition to the one already recorded inside
    # _llm_tool_loop's except block, double-counting a single real LLM
    # failure as two circuit-breaker failures. With threshold=2, a single
    # respond() failure must NOT open the breaker; only the second must.
    agent = OOAgent(llm_client=_AlwaysFailingLLMClient())
    await agent.initialize(AgentConfig(circuit_breaker_threshold=2))

    await agent.respond(Query(text="hello agent"))
    assert await agent._lifecycle.health_check() == "healthy"

    await agent.respond(Query(text="hello again"))
    assert await agent._lifecycle.health_check() == "degraded"

    await agent.dispose()
