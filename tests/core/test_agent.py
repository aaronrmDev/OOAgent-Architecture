"""tests/core/test_agent.py — OOAgent end-to-end Template Method (respond())."""

from __future__ import annotations

import pytest

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import (
    AgentConfig,
    CompletionChunk,
    CompletionResponse,
    ILLMClient,
    LifecycleError,
    Query,
    TokenUsage,
)
from ooagent.core.registry import ContextRegistry


class _StubLLMClient(ILLMClient):
    async def complete(self, request):
        return CompletionResponse(
            content="hello world", stop_reason="end_turn", usage=TokenUsage(input_tokens=1, output_tokens=1)
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


async def test_dispose_is_idempotent_by_raising_on_second_call() -> None:
    # Mirrors §17 CLAUDE.md's dispose-idempotency conformance requirement:
    # a second dispose() must not corrupt state, even though (per
    # core/lifecycle.ts) it raises LifecycleError rather than silently no-op-ing.
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())
    await agent.dispose()
    with pytest.raises(LifecycleError):
        await agent.dispose()


async def test_agent_id_is_generated_when_not_supplied() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    assert len(agent.agent_id) > 0
