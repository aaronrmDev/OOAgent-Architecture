"""tests/core/test_pipeline.py — ResponsePipeline (CoR) and ConstraintEngine."""

from __future__ import annotations

import pytest

from ooagent.core.pipeline import ConstraintEngine, ResponsePipeline, create_step
from ooagent.core.protocols import ConstraintViolationError, Query, Solution


@pytest.fixture(autouse=True)
def _reset_constraint_engine_singleton():
    ConstraintEngine.reset()
    yield
    ConstraintEngine.reset()


async def test_pipeline_runs_steps_in_order_and_merges_extras() -> None:
    async def step_a(query, ctx):
        return {"passed": True, "extras": {"a": 1}}

    async def step_b(query, ctx):
        return {"passed": True, "extras": {"b": 2}}

    pipeline = ResponsePipeline([create_step("a", step_a), create_step("b", step_b)])
    extras = await pipeline.run(Query(text="hi"), object())  # type: ignore[arg-type]
    assert extras == {"a": 1, "b": 2}


async def test_pipeline_raises_constraint_violation_on_failed_step() -> None:
    async def failing(query, ctx):
        return {"passed": False, "violation": "bad input"}

    pipeline = ResponsePipeline([create_step("failing", failing)])
    with pytest.raises(ConstraintViolationError) as exc_info:
        await pipeline.run(Query(text="hi"), object())  # type: ignore[arg-type]
    assert exc_info.value.invariant_name == "failing"


def test_pipeline_extend_returns_new_pipeline_with_combined_steps() -> None:
    async def noop(query, ctx):
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
