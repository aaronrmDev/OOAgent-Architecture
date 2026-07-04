"""tests/core/test_state.py — SessionState FSM and Memento behavior."""

from __future__ import annotations

import pytest

from ooagent.core.protocols import Command, FSMViolationError, Query, Solution
from ooagent.core.state import SessionState


def test_initial_state_is_idle_with_turn_zero() -> None:
    state = SessionState()
    assert state.fsm == "IDLE"
    assert state.turn == 0
    assert state.context_name == "NullContext"


def test_valid_transition_sequence_succeeds() -> None:
    state = SessionState()
    state.transition("GATHERING")
    state.transition("MODELING")
    state.transition("SOLVING")
    state.transition("VALIDATING")
    state.transition("DELIVERING")
    state.transition("IDLE")
    assert state.fsm == "IDLE"
    assert len(state.trace) == 6


def test_illegal_transition_raises_fsm_violation_error() -> None:
    state = SessionState()
    with pytest.raises(FSMViolationError):
        state.transition("SOLVING")  # IDLE -> SOLVING is not allowed


def test_snapshot_and_restore_round_trip() -> None:
    state = SessionState()
    state.set_context("Engineering")
    state.transition("GATHERING")
    memento = state.snapshot()
    state.transition("MODELING")
    state.restore(memento.id)
    assert state.fsm == "GATHERING"
    assert state.context_name == "Engineering"


def test_commit_increments_turn_and_reset_returns_to_idle() -> None:
    state = SessionState()
    state.transition("GATHERING")
    cmd = Command(
        id="cmd-1",
        query=Query(text="hi"),
        solution=Solution(content="ok", format="text", sources=[]),
        context_name="NullContext",
        trace=state.trace,
        timestamp=0.0,
    )
    state.commit(cmd)
    assert state.turn == 1
    state.reset()
    assert state.fsm == "IDLE"
    assert state.trace == []


def test_subscribe_notifies_observer_on_transition() -> None:
    state = SessionState()
    seen = []
    unsubscribe = state.subscribe(lambda fsm: seen.append(fsm))
    state.transition("GATHERING")
    assert seen == ["GATHERING"]
    unsubscribe()
    state.transition("MODELING")
    assert seen == ["GATHERING"]
