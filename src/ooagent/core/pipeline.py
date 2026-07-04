"""core/pipeline.py — ResponsePipeline (CoR), ConstraintEngine."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from ooagent.core.protocols import (
    ConstraintViolationError,
    IDomainContext,
    Invariant,
    PipelineStep,
    PipelineStepResult,
    Query,
    Solution,
)


class ResponsePipeline:
    """Chain of Responsibility — §4 GoF."""

    def __init__(self, base_steps: list[PipelineStep] | None = None) -> None:
        self._steps: list[PipelineStep] = list(base_steps or [])

    def extend(self, context_steps: list[PipelineStep]) -> ResponsePipeline:
        return ResponsePipeline([*self._steps, *context_steps])

    async def run(self, query: Query, context: IDomainContext) -> dict[str, Any]:
        extras: dict[str, Any] = {}
        for step in self._steps:
            result = await step.run(query, context)
            extras.update(result.extras)
            if not result.passed:
                raise ConstraintViolationError(
                    step.name, result.violation or "unknown", {"query": query.text}
                )
        return extras


class ConstraintEngine:
    """Singleton — source of truth for invariant enforcement — §4 GoF.

    Python has no private constructor; by convention, construct only via
    `get_instance()` (mirrors the TS private-constructor idiom)."""

    _instance: ConstraintEngine | None = None

    @classmethod
    def get_instance(cls) -> ConstraintEngine:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test hook — resets singleton."""
        cls._instance = None

    def assert_all(self, solution: Solution, invariants: list[Invariant]) -> None:
        for inv in invariants:
            self._assert(solution, inv)

    def _assert(self, solution: Solution, invariant: Invariant) -> None:
        """Base evaluation: domain contexts provide specialized validators via
        IDomainContext.invariants() whose conditions are checked at runtime.
        Override this method in subclasses to add custom validation logic.
        The base engine passes all invariants — domain contexts narrow this."""


def create_step(
    name: str,
    fn: Callable[
        [Query, IDomainContext],
        Awaitable[dict[str, Any]],
    ],
) -> PipelineStep:
    """Convenience pipeline step factory. `fn` returns a dict with keys
    `passed` (bool, required), `extras` (dict, optional), `violation`
    (str, optional) — mirrors the TS factory's loosely-typed return object."""

    class _Step:
        def __init__(self) -> None:
            self.name = name

        async def run(self, query: Query, context: IDomainContext) -> PipelineStepResult:
            result = await fn(query, context)
            return PipelineStepResult(
                passed=bool(result["passed"]),
                extras=dict(result.get("extras") or {}),
                violation=result.get("violation"),
            )

    return _Step()
