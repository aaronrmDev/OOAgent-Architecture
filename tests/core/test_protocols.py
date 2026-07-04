"""tests/core/test_protocols.py — sanity checks for core/protocols.py."""

from __future__ import annotations

import pytest

from ooagent.core.protocols import (
    AgentConfig,
    IAgent,
    ILLMClient,
    Query,
    ToolExecutionError,
)


def test_agent_config_has_expected_defaults() -> None:
    config = AgentConfig()
    assert config.max_retries == 3
    assert config.max_tool_rounds == 5
    assert config.circuit_breaker_threshold == 5


def test_query_is_a_frozen_dataclass() -> None:
    q = Query(text="hello")
    with pytest.raises(Exception):
        q.text = "changed"  # type: ignore[misc]


def test_iagent_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        IAgent()  # type: ignore[abstract]


def test_illmclient_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        ILLMClient()  # type: ignore[abstract]


def test_tool_execution_error_preserves_message_and_call_args() -> None:
    err = ToolExecutionError("calculator", {"expression": "1+1"}, ValueError("boom"))
    assert "Tool execution failed: calculator" in str(err)
    assert err.call_args == {"expression": "1+1"}
    assert err.tool_name == "calculator"
