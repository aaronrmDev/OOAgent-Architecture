"""tests/core/test_pipeline.py — ResponsePipeline (CoR) and ConstraintEngine."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest

from ooagent.core.pipeline import ConstraintEngine, ResponsePipeline, create_step
from ooagent.core.protocols import ConstraintViolationError, Query, Solution


@pytest.fixture(autouse=True)
def _reset_constraint_engine_singleton() -> Generator[None, None, None]:
    ConstraintEngine.reset()
    yield
    ConstraintEngine.reset()


async def test_pipeline_runs_steps_in_order_and_merges_extras() -> None:
    async def step_a(query: Query, ctx: Any) -> dict[str, Any]:
        return {"passed": True, "extras": {"a": 1}}

    async def step_b(query: Query, ctx: Any) -> dict[str, Any]:
        return {"passed": True, "extras": {"b": 2}}

    pipeline = ResponsePipeline([create_step("a", step_a), create_step("b", step_b)])
    extras = await pipeline.run(Query(text="hi"), object())
    assert extras == {"a": 1, "b": 2}


async def test_pipeline_raises_constraint_violation_on_failed_step() -> None:
    async def failing(query: Query, ctx: Any) -> dict[str, Any]:
        return {"passed": False, "violation": "bad input"}

    pipeline = ResponsePipeline([create_step("failing", failing)])
    with pytest.raises(ConstraintViolationError) as exc_info:
        await pipeline.run(Query(text="hi"), object())
    assert exc_info.value.invariant_name == "failing"


def test_pipeline_extend_returns_new_pipeline_with_combined_steps() -> None:
    async def noop(query: Query, ctx: Any) -> dict[str, Any]:
        return {"passed": True}

    base = ResponsePipeline([create_step("base", noop)])
    extended = base.extend([create_step("extra", noop)])
    assert len(extended._steps) == 2
    assert len(base._steps) == 1


def test_constraint_engine_is_a_singleton() -> None:
    a = ConstraintEngine.get_instance()
    b = ConstraintEngine.get_instance()
    assert a is b


def test_constraint_engine_assert_all_does_not_raise_by_default() -> None:
    engine = ConstraintEngine.get_instance()
    solution = Solution(content="ok", format="text", sources=[])
    engine.assert_all(solution, [])  # should not raise


def test_constraint_engine_raises_on_failing_error_severity_invariant() -> None:
    from ooagent.core.protocols import Invariant

    engine = ConstraintEngine.get_instance()
    solution = Solution(content="ok", format="text", sources=[])
    failing = Invariant(
        name="always-fails",
        condition="never true",
        severity="error",
        rationale="test",
        check=lambda s: False,
    )
    with pytest.raises(ConstraintViolationError) as exc_info:
        engine.assert_all(solution, [failing])
    assert exc_info.value.invariant_name == "always-fails"


def test_constraint_engine_does_not_raise_on_failing_warning_severity_invariant() -> None:
    from ooagent.core.protocols import Invariant

    engine = ConstraintEngine.get_instance()
    solution = Solution(content="ok", format="text", sources=[])
    warning = Invariant(
        name="soft-check",
        condition="never true",
        severity="warning",
        rationale="test",
        check=lambda s: False,
    )
    engine.assert_all(solution, [warning])  # should not raise


def test_constraint_engine_does_not_raise_on_passing_invariant() -> None:
    from ooagent.core.protocols import Invariant

    engine = ConstraintEngine.get_instance()
    solution = Solution(content="ok", format="text", sources=[])
    passing = Invariant(
        name="always-passes",
        condition="x",
        severity="error",
        rationale="test",
        check=lambda s: True,
    )
    engine.assert_all(solution, [passing])  # should not raise


def test_constraint_engine_does_not_raise_when_invariant_has_no_check() -> None:
    from ooagent.core.protocols import Invariant

    engine = ConstraintEngine.get_instance()
    solution = Solution(content="ok", format="text", sources=[])
    no_check = Invariant(
        name="undeclared",
        condition="x",
        severity="error",
        rationale="test",
    )
    engine.assert_all(solution, [no_check])  # should not raise


async def test_empty_query_step_fails_on_blank_text() -> None:
    from ooagent.core.pipeline import empty_query_step

    step = empty_query_step()
    result = await step.run(Query(text="   "), object())
    assert result.passed is False
    assert "empty" in (result.violation or "").lower()


async def test_empty_query_step_passes_on_non_blank_text() -> None:
    from ooagent.core.pipeline import empty_query_step

    step = empty_query_step()
    result = await step.run(Query(text="hello"), object())
    assert result.passed is True
