"""tests/examples/test_examples.py — golden-path examples run end-to-end."""

from __future__ import annotations

import pytest

from examples.minimal_agent import main as minimal_main


async def test_minimal_agent_runs_and_prints_artifact(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await minimal_main()
    captured = capsys.readouterr()
    assert "format:  text" in captured.out
    assert "content: Hello! I'm a validated OOAgent response." in captured.out
