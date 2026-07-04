"""tests/adapters/test_tools_base.py — BaseTool.to_vendor_spec() per vendor."""

from __future__ import annotations

from typing import Any

import pytest

from ooagent.adapters.tools.base import BaseTool
from ooagent.core.protocols import JSONSchema, ToolExecutionError


class _EchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes input"

    def input_schema(self) -> JSONSchema:
        return {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}

    async def execute(self, args: dict[str, Any]) -> Any:
        self._validate_args(args)
        return {"echo": args["text"]}


async def test_execute_with_valid_args_succeeds() -> None:
    tool = _EchoTool()
    result = await tool.execute({"text": "hi"})
    assert result == {"echo": "hi"}


async def test_execute_with_missing_required_arg_raises_tool_execution_error() -> None:
    tool = _EchoTool()
    with pytest.raises(ToolExecutionError):
        await tool.execute({})


def test_to_vendor_spec_anthropic_shape() -> None:
    spec = _EchoTool().to_vendor_spec("anthropic")
    assert spec["name"] == "echo"
    assert "input_schema" in spec


def test_to_vendor_spec_openai_and_ollama_share_function_shape() -> None:
    openai_spec = _EchoTool().to_vendor_spec("openai")
    ollama_spec = _EchoTool().to_vendor_spec("ollama")
    assert openai_spec["type"] == "function"
    assert ollama_spec["type"] == "function"
    assert openai_spec["function"]["name"] == "echo"


def test_to_vendor_spec_gemini_shape() -> None:
    spec = _EchoTool().to_vendor_spec("gemini")
    assert spec["function_declarations"][0]["name"] == "echo"
