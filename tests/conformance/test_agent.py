"""tests/conformance/test_agent.py — IAgent conformance suite (§17 CLAUDE.md).

Mirrors testing/conformance/agent.conformance.test.ts, where every case is a
`test.todo(...)` placeholder — none are implemented there, so none are
implemented here either (except dispose-idempotency, now implemented in the
Python port — see LifecycleManager.dispose() in core/lifecycle.py). Fleshing
the rest out with real assertions is phase-3 hardening work, not translation
scope for this port.
"""

from __future__ import annotations

import pytest

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import (
    AgentConfig,
    CompletionChunk,
    CompletionResponse,
    ILLMClient,
    TokenUsage,
)


class _StubLLMClient(ILLMClient):
    async def complete(self, request):
        return CompletionResponse(
            content="hello",
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


@pytest.mark.skip(
    reason="TODO: respond(emptyQuery) returns ConstraintViolation artifact — not throw"
)
def test_respond_empty_query_returns_constraint_violation_artifact_not_throw() -> None: ...


@pytest.mark.skip(reason="TODO: FSM is IDLE before and after each complete turn")
def test_fsm_is_idle_before_and_after_each_complete_turn() -> None: ...


@pytest.mark.skip(reason="TODO: SessionState.turn increments by exactly 1 per successful turn")
def test_session_state_turn_increments_by_exactly_1_per_successful_turn() -> None: ...


async def test_dispose_is_idempotent_calling_twice_does_not_throw() -> None:
    agent = OOAgent(llm_client=_StubLLMClient())
    await agent.initialize(AgentConfig())
    await agent.dispose()
    await agent.dispose()  # must not raise


@pytest.mark.skip(reason="TODO: respond() after dispose() throws LifecycleError")
def test_respond_after_dispose_throws_lifecycle_error() -> None: ...
