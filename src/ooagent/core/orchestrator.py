"""core/orchestrator.py — MultiAgentOrchestrator, SignalBus."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

from ooagent.core.protocols import IDomainContext, IOrchestrator, Query, Solution

_logger = logging.getLogger("ooagent.orchestrator")

T = TypeVar("T")
SignalHandler = Callable[[T], None]


class SignalBus:
    """Mediator — collaborators communicate only through SignalBus — §4 GoF."""

    def __init__(self) -> None:
        self._handlers: dict[str, set[SignalHandler[Any]]] = {}

    def publish(self, signal: str, payload: Any) -> None:
        handlers = self._handlers.get(signal)
        if not handlers:
            return
        for handler in list(handlers):
            try:
                handler(payload)
            except Exception:
                _logger.exception('[SignalBus] Handler error for signal "%s"', signal)

    def subscribe(self, signal: str, handler: SignalHandler[Any]) -> Callable[[], None]:
        self._handlers.setdefault(signal, set()).add(handler)

        def unsubscribe() -> None:
            self._handlers.get(signal, set()).discard(handler)

        return unsubscribe


class _Semaphore:
    """Bounds parallel API calls — §13 CLAUDE.md. A thin wrapper over
    asyncio.Semaphore kept as its own class to mirror the TS source's
    explicit Semaphore type."""

    def __init__(self, limit: int) -> None:
        self._sem = asyncio.Semaphore(limit)

    async def run(self, fn: Callable[[], Awaitable[T]]) -> T:
        async with self._sem:
            return await fn()


class SpecialistAgent(Protocol):
    async def respond(self, query: Query) -> Any: ...


SpecialistAgentFactory = Callable[[IDomainContext], SpecialistAgent]


class MultiAgentOrchestrator(IOrchestrator):
    """Multi-agent orchestration — §13 CLAUDE.md."""

    def __init__(
        self,
        agent_factory: SpecialistAgentFactory,
        concurrency: int = 5,
    ) -> None:
        self._agent_factory = agent_factory
        self._bus = SignalBus()
        self._semaphore = _Semaphore(concurrency)

    @property
    def bus(self) -> SignalBus:
        return self._bus

    async def dispatch(
        self, query: Query, contexts: list[IDomainContext]
    ) -> list[Solution]:
        return await asyncio.gather(
            *(
                self._semaphore.run(lambda ctx=ctx: self._run_specialist(query, ctx))
                for ctx in contexts
            )
        )

    async def synthesize(self, solutions: list[Solution], original: Query) -> Solution:
        """Default: concatenate. Override with a meta-agent LLM call when available."""
        content = "\n\n---\n\n".join(s.content for s in solutions)
        return Solution(
            content=content,
            format="text",
            sources=[src for s in solutions for src in s.sources],
        )

    async def _run_specialist(self, query: Query, ctx: IDomainContext) -> Solution:
        try:
            agent = self._agent_factory(ctx)
            raw = await agent.respond(query)
            solution = Solution(
                content=raw if isinstance(raw, str) else json.dumps(raw),
                format="text",
                sources=[],
            )
            self._bus.publish("specialist.done", {"context": ctx.name, "solution": solution})
            return solution
        except Exception as err:
            return Solution(
                content=f"[SpecialistError] {ctx.name}: {err}",
                format="text",
                sources=[],
            )
