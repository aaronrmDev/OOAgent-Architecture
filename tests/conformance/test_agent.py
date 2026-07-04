"""tests/conformance/test_agent.py — IAgent conformance suite (§17 CLAUDE.md).

Mirrors testing/conformance/agent.conformance.test.ts, where every case is a
`test.todo(...)` placeholder — none are implemented there, so none are
implemented here either. Fleshing these out with real assertions is
phase-3 hardening work, not translation scope for this port.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="TODO: respond(emptyQuery) returns ConstraintViolation artifact — not throw"
)
def test_respond_empty_query_returns_constraint_violation_artifact_not_throw() -> None: ...


@pytest.mark.skip(reason="TODO: FSM is IDLE before and after each complete turn")
def test_fsm_is_idle_before_and_after_each_complete_turn() -> None: ...


@pytest.mark.skip(reason="TODO: SessionState.turn increments by exactly 1 per successful turn")
def test_session_state_turn_increments_by_exactly_1_per_successful_turn() -> None: ...


@pytest.mark.skip(reason="TODO: dispose() is idempotent — calling twice does not throw")
def test_dispose_is_idempotent_calling_twice_does_not_throw() -> None: ...


@pytest.mark.skip(reason="TODO: respond() after dispose() throws LifecycleError")
def test_respond_after_dispose_throws_lifecycle_error() -> None: ...
