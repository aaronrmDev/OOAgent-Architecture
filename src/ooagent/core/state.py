"""core/state.py — SessionState, FSM, Memento, Command."""

from __future__ import annotations

import time
import uuid
from collections import OrderedDict

from ooagent.core.protocols import (
    AgentFSMState,
    Command,
    FSMTrace,
    FSMTraceEntry,
    FSMViolationError,
    ISessionState,
    Memento,
    StateObserver,
    Unsubscribe,
)

# Valid FSM transitions per CLAUDE.md §12
VALID_TRANSITIONS: dict[AgentFSMState, set[AgentFSMState]] = {
    "IDLE": {"GATHERING"},
    "GATHERING": {"MODELING", "AWAITING", "FAILURE"},
    "AWAITING": {"MODELING", "FAILURE"},
    "MODELING": {"SOLVING", "FAILURE"},
    "SOLVING": {"VALIDATING", "FAILURE"},
    "VALIDATING": {"DELIVERING", "FAILURE"},
    "DELIVERING": {"IDLE"},
    "FAILURE": {"DELIVERING"},
}


class SessionState(ISessionState):
    def __init__(self, max_mementos: int = 100) -> None:
        self._fsm: AgentFSMState = "IDLE"
        self._turn = 0
        self._context_name = "NullContext"
        self._scratch: dict[str, object] = {}
        self._trace: FSMTrace = []
        self._mementos: OrderedDict[str, Memento] = OrderedDict()
        self._command_log: list[Command] = []
        self._observers: set[StateObserver] = set()
        self._max_mementos = max_mementos

    @property
    def fsm(self) -> AgentFSMState:
        return self._fsm

    @property
    def turn(self) -> int:
        return self._turn

    @property
    def context_name(self) -> str:
        return self._context_name

    @property
    def trace(self) -> FSMTrace:
        return list(self._trace)

    @property
    def history(self) -> list[Command]:
        return list(self._command_log)

    def transition(self, to: AgentFSMState) -> None:
        allowed = VALID_TRANSITIONS.get(self._fsm, set())
        if to not in allowed:
            raise FSMViolationError(self._fsm, to, self.trace)
        self._fsm = to
        self._trace.append(FSMTraceEntry(state=to, timestamp=time.time()))
        self._notify_observers()

    def set_context(self, name: str) -> None:
        self._context_name = name

    def snapshot(self) -> Memento:
        if len(self._mementos) >= self._max_mementos:
            self._mementos.popitem(last=False)  # evict least-recently-used
        memento = Memento(
            id=str(uuid.uuid4()),
            fsm=self._fsm,
            turn=self._turn,
            context_name=self._context_name,
            scratch=dict(self._scratch),
            timestamp=time.time(),
        )
        self._mementos[memento.id] = memento
        return memento

    def restore(self, id: str) -> None:
        memento = self._mementos.get(id)
        if memento is None:
            raise ValueError(f"Memento not found: {id}")
        self._mementos.move_to_end(id)  # mark as most-recently-used
        self._fsm = memento.fsm
        self._turn = memento.turn
        self._context_name = memento.context_name
        self._scratch = dict(memento.scratch)
        self._trace = []
        self._notify_observers()

    def commit(self, cmd: Command) -> None:
        self._command_log.append(cmd)
        self._turn += 1
        self._notify_observers()

    def subscribe(self, obs: StateObserver) -> Unsubscribe:
        self._observers.add(obs)

        def unsubscribe() -> None:
            self._observers.discard(obs)

        return unsubscribe

    async def flush(self) -> None:
        """Base: no-op. Override for persistence."""

    def reset(self) -> None:
        self._fsm = "IDLE"
        self._trace = []
        self._scratch = {}
        self._notify_observers()

    def _notify_observers(self) -> None:
        for obs in self._observers:
            obs(self._fsm)
