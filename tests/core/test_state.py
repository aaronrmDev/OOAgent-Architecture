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


def test_restore_also_restores_turn() -> None:
    state = SessionState()
    state.transition("GATHERING")
    # Take a snapshot with turn=0
    memento = state.snapshot()
    assert memento.turn == 0

    # Commit some commands to change turn
    cmd1 = Command(
        id="cmd-1",
        query=Query(text="first"),
        solution=Solution(content="result1", format="text", sources=[]),
        context_name="NullContext",
        trace=state.trace,
        timestamp=0.0,
    )
    state.commit(cmd1)
    assert state.turn == 1

    cmd2 = Command(
        id="cmd-2",
        query=Query(text="second"),
        solution=Solution(content="result2", format="text", sources=[]),
        context_name="NullContext",
        trace=state.trace,
        timestamp=1.0,
    )
    state.commit(cmd2)
    assert state.turn == 2

    # Restore to the earlier memento and verify turn is also restored
    state.restore(memento.id)
    assert state.turn == 0, "restore() must also restore turn from memento"
    assert state.fsm == "GATHERING"


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


def test_snapshot_eviction_is_lru_not_fifo() -> None:
    state = SessionState(max_mementos=2)
    state.transition("GATHERING")
    a = state.snapshot()
    state.transition("MODELING")
    b = state.snapshot()

    state.restore(a.id)  # touches `a` — makes it more-recently-used than `b`

    c = state.snapshot()  # 3rd snapshot exceeds max_mementos=2

    with pytest.raises(ValueError):
        state.restore(b.id)  # `b` was least-recently-used — evicted
    state.restore(a.id)  # must not raise — still present
    state.restore(c.id)  # must not raise — still present


def test_degraded_is_not_a_valid_fsm_state() -> None:
    from ooagent.core.state import VALID_TRANSITIONS

    assert "DEGRADED" not in VALID_TRANSITIONS
    for targets in VALID_TRANSITIONS.values():
        assert "DEGRADED" not in targets
