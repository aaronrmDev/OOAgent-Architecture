"""tests/conformance/test_agent.py — IAgent conformance suite (§17 CLAUDE.md)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import (
    AgentConfig,
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    ILLMClient,
    LifecycleError,
    LLMVendor,
    Query,
    TokenUsage,
)


class _StubLLMClient(ILLMClient):
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            content="hello",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    async def ping(self) -> bool:
        # Defensive: present whether or not the sibling lifecycle-health-and-
        # timeouts plan (which adds ILLMClient.ping() as a new abstract
        # method) has landed yet — harmless extra method if it hasn't.
        return True

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncIterator[CompletionChunk]:
        yield CompletionChunk(delta="hi", done=True)

    @property
    def model_id(self) -> str:
        return "stub-1"

    @property
    def vendor(self) -> LLMVendor:
        return "anthropic"

    @property
    def max_tokens(self) -> int:
        return 4096

    @property
    def supports_tools(self) -> bool:
        return False


async def test_respond_empty_query_returns_constraint_violation_artifact_not_throw() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())

    artifact = await agent.respond(Query(text=""))

    assert "[ConstraintViolation]" in artifact.content
    assert agent.state.fsm == "IDLE"
    await agent.dispose()


async def test_fsm_is_idle_before_and_after_each_complete_turn() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())

    assert agent.state.fsm == "IDLE"
    await agent.respond(Query(text="hello agent"))
    assert agent.state.fsm == "IDLE"

    await agent.dispose()


async def test_session_state_turn_increments_by_exactly_1_per_successful_turn() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())

    assert agent.state.turn == 0
    await agent.respond(Query(text="hello agent"))
    assert agent.state.turn == 1
    await agent.respond(Query(text="hello again"))
    assert agent.state.turn == 2

    await agent.dispose()


async def test_dispose_is_idempotent_calling_twice_does_not_throw() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())
    await agent.dispose()
    await agent.dispose()  # must not raise


async def test_respond_after_dispose_throws_lifecycle_error() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())
    await agent.dispose()

    with pytest.raises(LifecycleError):
        await agent.respond(Query(text="hello"))
