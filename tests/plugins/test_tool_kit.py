"""tests/plugins/test_tool_kit.py — CalculatorTool, DateTimeTool, ToolKitPlugin."""

from __future__ import annotations

import re

import pytest

from ooagent.core.protocols import ToolExecutionError
from ooagent.plugins.tool_kit import CalculatorTool, DateTimeTool, ToolKitPlugin


async def test_calculator_evaluates_arithmetic_expression() -> None:
    tool = CalculatorTool()
    result = await tool.execute({"expression": "(2 + 3) * 4 ** 2"})
    assert result["result"] == 80.0


async def test_calculator_applies_unary_minus_after_exponentiation() -> None:
    tool = CalculatorTool()
    result = await tool.execute({"expression": "-2 ** 2"})
    assert result["result"] == -4.0


async def test_calculator_allows_negative_exponent() -> None:
    tool = CalculatorTool()
    result = await tool.execute({"expression": "2 ** -2"})
    assert result["result"] == 0.25


async def test_calculator_rejects_empty_expression() -> None:
    tool = CalculatorTool()
    with pytest.raises(ToolExecutionError):
        await tool.execute({"expression": ""})


async def test_calculator_rejects_division_by_zero() -> None:
    tool = CalculatorTool()
    with pytest.raises(ToolExecutionError):
        await tool.execute({"expression": "1 / 0"})


async def test_datetime_tool_returns_iso_timestamp() -> None:
    tool = DateTimeTool()
    result = await tool.execute({})
    assert result["iso"].endswith("Z")
    assert result["timezone"] == "UTC"


async def test_datetime_tool_returns_correct_numeric_offset_for_non_utc_timezone() -> None:
    tool = DateTimeTool()
    result = await tool.execute({"timezone": "America/New_York"})
    assert result["timezone"] == "America/New_York"
    assert not result["iso"].endswith("Z"), (
        "non-UTC time must not be labeled with a UTC 'Z' suffix"
    )
    assert re.search(r"[+-]\d{2}:\d{2}$", result["iso"]), result["iso"]


async def test_datetime_tool_still_returns_z_suffix_for_explicit_utc() -> None:
    tool = DateTimeTool()
    result = await tool.execute({"timezone": "UTC"})
    assert result["iso"].endswith("Z")
    assert result["timezone"] == "UTC"


def test_tool_kit_plugin_contributes_all_three_tools_by_default() -> None:
    plugin = ToolKitPlugin()
    contributions = plugin.contributes()
    names = {t.name for t in contributions.tools}
    assert names == {"datetime", "calculator", "http_fetch"}
