"""tests/examples/test_examples.py — golden-path examples run end-to-end."""

from __future__ import annotations

import pytest

from examples.domain_context_agent import main as domain_context_main
from examples.minimal_agent import main as minimal_main
from examples.tool_enabled_agent import main as tool_main


async def test_minimal_agent_runs_and_prints_artifact(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await minimal_main()
    captured = capsys.readouterr()
    assert "format:  text" in captured.out
    assert "content: Hello! I'm a validated OOAgent response." in captured.out


async def test_tool_enabled_agent_registers_calculator(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await tool_main()
    captured = capsys.readouterr()
    assert "registered tools: ['calculator']" in captured.out


async def test_domain_context_agent_resolves_unit_conversion_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await domain_context_main()
    captured = capsys.readouterr()
    assert "resolved context: UnitConversion v1.0" in captured.out
