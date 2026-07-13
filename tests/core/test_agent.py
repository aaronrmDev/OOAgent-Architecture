"""tests/core/test_agent.py — OOAgent end-to-end Template Method (respond())."""

from __future__ import annotations

import pytest

from ooagent.adapters.tools.base import BaseTool
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
    ToolCall,
)
from ooagent.core.registry import ContextRegistry


class _StubLLMClient(ILLMClient):
    async def complete(self, request):
        return CompletionResponse(
            content="hello world",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    async def ping(self) -> bool:
        return True

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


async def test_constraint_engine_is_injectable_and_defaults_to_singleton() -> None:
    from ooagent.core.pipeline import ConstraintEngine

    default_agent = OOAgent(llm_client=_StubLLMClient())
    assert default_agent._constraint_engine is ConstraintEngine.get_instance()

    custom_engine = ConstraintEngine()
    injected_agent = OOAgent(llm_client=_StubLLMClient(), constraint_engine=custom_engine)
    assert injected_agent._constraint_engine is custom_engine
    assert injected_agent._constraint_engine is not ConstraintEngine.get_instance()


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

    async def ping(self) -> bool:
        return True

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


class _ToolUseLLMClient(ILLMClient):
    """Returns one tool_use round for `tool_name`, then end_turn."""

    def __init__(self, tool_name: str) -> None:
        self._tool_name = tool_name
        self._calls = 0

    async def complete(self, request):
        self._calls += 1
        if self._calls == 1:
            return CompletionResponse(
                content="",
                stop_reason="tool_use",
                usage=TokenUsage(input_tokens=1, output_tokens=1),
                tool_calls=[ToolCall(id="call-1", name=self._tool_name, args={"text": "hi"})],
            )
        return CompletionResponse(
            content="done",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    async def ping(self) -> bool:
        return True

    async def stream(self, request):
        yield CompletionChunk(delta="", done=True)

    @property
    def model_id(self):
        return "stub-tool-use"

    @property
    def vendor(self):
        return "anthropic"

    @property
    def max_tokens(self):
        return 4096

    @property
    def supports_tools(self):
        return True


class _EchoTool(BaseTool):
    name = "echo"
    description = "Echoes input text."

    def input_schema(self):
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    async def execute(self, args):
        return {"echo": args["text"]}


class _RaisingTool(BaseTool):
    name = "raiser"
    description = "Always raises."

    def input_schema(self):
        return {"type": "object", "properties": {}}

    async def execute(self, args):
        raise ValueError("tool exploded")


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


async def test_tool_call_events_fire_on_success() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_ToolUseLLMClient("echo"), telemetry=telemetry)
    agent._tool_registry.register(_EchoTool())
    await agent.initialize(AgentConfig())

    await agent.respond(Query(text="use the echo tool"))

    assert ("tool.call_started", {"tool": "echo"}) in telemetry.events
    assert ("tool.call_completed", {"tool": "echo"}) in telemetry.events
    started_idx = telemetry.events.index(("tool.call_started", {"tool": "echo"}))
    completed_idx = telemetry.events.index(("tool.call_completed", {"tool": "echo"}))
    assert started_idx < completed_idx

    await agent.dispose()


async def test_tool_call_failed_event_fires_when_tool_raises() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_ToolUseLLMClient("raiser"), telemetry=telemetry)
    agent._tool_registry.register(_RaisingTool())
    await agent.initialize(AgentConfig())

    await agent.respond(Query(text="use the raiser tool"))

    assert ("tool.call_started", {"tool": "raiser"}) in telemetry.events
    assert (
        "tool.call_failed",
        {"tool": "raiser", "error_type": "ValueError"},
    ) in telemetry.events

    await agent.dispose()


async def test_tool_call_failed_event_fires_when_tool_not_found() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_ToolUseLLMClient("missing"), telemetry=telemetry)
    await agent.initialize(AgentConfig())

    await agent.respond(Query(text="use a missing tool"))

    assert (
        "tool.call_failed",
        {"tool": "missing", "error_type": "ToolNotFound"},
    ) in telemetry.events
    assert ("tool.call_started", {"tool": "missing"}) not in telemetry.events

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


async def test_turn_failed_event_fires_recoverable_true_on_llm_failure() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_AlwaysFailingLLMClient(), telemetry=telemetry)
    await agent.initialize(AgentConfig())

    await agent.respond(Query(text="hello agent"))

    assert (
        "turn.failed",
        {"context": "NullContext", "error_type": "RuntimeError", "recoverable": True},
    ) in telemetry.events

    await agent.dispose()


async def test_turn_failed_event_fires_recoverable_false_on_delivering_failure() -> None:
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_StubLLMClient(), telemetry=telemetry)
    await agent.initialize(AgentConfig())

    def _boom(artifact, provenance):
        raise RuntimeError("boom")

    agent._decorator.add_decorator(_boom)

    await agent.respond(Query(text="hello agent"))

    assert (
        "turn.failed",
        {"context": "NullContext", "error_type": "RuntimeError", "recoverable": False},
    ) in telemetry.events

    await agent.dispose()


async def test_context_resolution_failure_routes_through_failure_state_not_bypass() -> None:
    # §12 CLAUDE.md: "FAILURE always leads to DELIVERING (emit error artifact)
    # then IDLE." A failure during the GATHERING prelude (context resolution)
    # has GATHERING -> FAILURE as a legal transition (state.py VALID_TRANSITIONS),
    # so it must not use the FSM-bypassing _handle_unrecoverable_failure path.
    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_StubLLMClient(), telemetry=telemetry)
    await agent.initialize(AgentConfig())

    def _boom(query):
        raise RuntimeError("resolve boom")

    agent._ctx_registry.resolve = _boom  # type: ignore[method-assign]

    artifact = await agent.respond(Query(text="hello agent"))

    assert "resolve boom" in artifact.content
    assert agent.state.fsm == "IDLE"
    assert (
        "turn.failed",
        {"context": "unknown", "error_type": "RuntimeError", "recoverable": True},
    ) in telemetry.events

    await agent.dispose()


async def test_tool_execution_times_out_and_reports_failure_not_hang() -> None:
    import asyncio

    class _SlowTool(BaseTool):
        name = "slow"
        description = "Never returns in time."

        def input_schema(self):
            return {"type": "object", "properties": {}}

        async def execute(self, args):
            await asyncio.sleep(60)
            return {"ok": True}

    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_ToolUseLLMClient("slow"), telemetry=telemetry)
    agent._tool_registry.register(_SlowTool())
    await agent.initialize(AgentConfig(tool_timeout_ms=50))

    artifact = await agent.respond(Query(text="use the slow tool"))

    assert ("tool.call_started", {"tool": "slow"}) in telemetry.events
    failed_events = [
        e for e in telemetry.events if e[0] == "tool.call_failed" and e[1]["tool"] == "slow"
    ]
    assert len(failed_events) == 1
    assert failed_events[0][1]["error_type"] == "TimeoutError"
    assert artifact is not None

    await agent.dispose()


async def test_llm_call_times_out_and_is_handled_as_a_failure() -> None:
    import asyncio

    class _SlowLLMClient(ILLMClient):
        async def complete(self, request):
            await asyncio.sleep(60)
            return CompletionResponse(
                content="too slow",
                stop_reason="end_turn",
                usage=TokenUsage(input_tokens=1, output_tokens=1),
            )

        async def ping(self) -> bool:
            return True

        async def stream(self, request):
            yield CompletionChunk(delta="", done=True)

        @property
        def model_id(self):
            return "slow-1"

        @property
        def vendor(self):
            return "anthropic"

        @property
        def max_tokens(self):
            return 4096

        @property
        def supports_tools(self):
            return False

    telemetry = _RecordingTelemetry()
    agent = OOAgent(llm_client=_SlowLLMClient(), telemetry=telemetry)
    await agent.initialize(AgentConfig(turn_timeout_ms=50))

    artifact = await agent.respond(Query(text="hello agent"))

    failed_events = [e for e in telemetry.events if e[0] == "llm.call_failed"]
    assert len(failed_events) == 1
    assert failed_events[0][1]["error_type"] == "TimeoutError"
    assert artifact is not None
    assert agent.state.fsm == "IDLE"

    await agent.dispose()
