"""tests/conformance/test_tool.py — ITool conformance suite (§17 CLAUDE.md).

Exercises the concrete DateTimeTool / CalculatorTool from
plugins/tool_kit/ (Task 16) — mirrors testing/conformance/tool.conformance.test.ts.
"""

from __future__ import annotations

import json

import httpx
import pytest

from ooagent.core.protocols import ToolExecutionError
from ooagent.plugins.tool_kit.calculator_tool import CalculatorTool
from ooagent.plugins.tool_kit.datetime_tool import DateTimeTool
from ooagent.plugins.tool_kit.http_fetch_tool import HttpFetchTool, HttpFetchToolOptions

date_tool = DateTimeTool()
calc_tool = CalculatorTool()


async def test_execute_valid_args_returns_result_without_throwing_datetime_tool() -> None:
    result = await date_tool.execute({})
    assert result is not None, "execute(valid_args) must return a result"


async def test_execute_valid_args_returns_result_without_throwing_calculator_tool() -> None:
    result = await calc_tool.execute({"expression": "2 + 2"})
    assert result is not None, "execute(valid_args) must return a result"


async def test_execute_invalid_args_throws_tool_execution_error_for_calculator_tool() -> None:
    with pytest.raises(ToolExecutionError):
        await calc_tool.execute({"expression": "not_a_number @@@ !!!"})


def test_to_vendor_spec_returns_valid_json_for_anthropic_vendor() -> None:
    spec = date_tool.to_vendor_spec("anthropic")
    payload = json.dumps(spec)
    assert len(payload) > 0, "to_vendor_spec() must return a non-empty JSON-serializable object"
    assert isinstance(spec, dict), "to_vendor_spec() must return an object"


def test_to_vendor_spec_returns_valid_json_for_openai_vendor() -> None:
    spec = calc_tool.to_vendor_spec("openai")
    assert len(json.dumps(spec)) > 0, "to_vendor_spec() returns valid JSON for openai"


def test_name_and_description_are_non_empty_strings() -> None:
    assert len(date_tool.name) > 0, "tool.name must be non-empty"
    assert len(date_tool.description) > 0, "tool.description must be non-empty"


# ── HttpFetchTool conformance tests ──────────────────────────────────────


def test_http_fetch_tool_name_and_description_are_non_empty() -> None:
    tool = HttpFetchTool()
    assert tool.name == "http_fetch"
    assert len(tool.description) > 0


def test_http_fetch_tool_to_vendor_spec_is_json_serializable() -> None:
    tool = HttpFetchTool()
    spec = tool.to_vendor_spec("anthropic")
    json.dumps(spec)  # must not raise


async def test_http_fetch_tool_rejects_non_https_url_without_network_call() -> None:
    tool = HttpFetchTool()
    with pytest.raises(ToolExecutionError):
        await tool.execute({"url": "http://example.com/data"})


async def test_http_fetch_tool_rejects_disallowed_host() -> None:
    tool = HttpFetchTool(HttpFetchToolOptions(allowed_hosts=["example.com"]))
    with pytest.raises(ToolExecutionError):
        await tool.execute({"url": "https://evil.example.org/data"})


async def test_http_fetch_tool_executes_successfully_against_a_mock_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok", headers={"content-type": "text/plain"})

    real_async_client = httpx.AsyncClient

    def _mock_client(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(_handler)
        return real_async_client(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", _mock_client)

    tool = HttpFetchTool()
    result = await tool.execute({"url": "https://example.com/data"})
    assert result["status"] == 200
    assert result["body"] == "ok"
