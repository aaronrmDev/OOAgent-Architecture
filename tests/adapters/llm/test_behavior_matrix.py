"""tests/adapters/llm/test_behavior_matrix.py — cross-adapter behavior matrix.

Same assertions run against all 4 real LLM adapters via the shared
ADAPTER_CASES list (conftest.py), proving the ILLMClient contract holds
uniformly where the adapters actually agree (CLAUDE.md §5's Adapter
pattern entry). Where they genuinely disagree, see
test_adapter_specific_behaviors.py instead — those divergences are
deliberately NOT asserted here.
"""

from __future__ import annotations

import httpx
import pytest

from ooagent.core.protocols import CompletionRequest, Message

from .conftest import ADAPTER_CASE_IDS, ADAPTER_CASES, AdapterCase, MockTransportInstaller


@pytest.mark.parametrize("case", ADAPTER_CASES, ids=ADAPTER_CASE_IDS)
def test_adapter_exposes_expected_vendor(case: AdapterCase) -> None:
    client = case.make_client()
    assert client.vendor == case.vendor


@pytest.mark.parametrize("case", ADAPTER_CASES, ids=ADAPTER_CASE_IDS)
def test_adapter_defaults_to_non_empty_model_id(case: AdapterCase) -> None:
    client = case.make_client()
    assert client.model_id != ""


@pytest.mark.parametrize("case", ADAPTER_CASES, ids=ADAPTER_CASE_IDS)
def test_adapter_defaults_to_positive_max_tokens(case: AdapterCase) -> None:
    client = case.make_client()
    assert client.max_tokens > 0


@pytest.mark.parametrize("case", ADAPTER_CASES, ids=ADAPTER_CASE_IDS)
async def test_adapter_complete_returns_valid_response_on_success(
    case: AdapterCase, mock_transport: MockTransportInstaller
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=case.success_body)

    mock_transport(handler)
    client = case.make_client()
    response = await client.complete(
        CompletionRequest(messages=[Message(role="user", content="hi")])
    )
    assert response.content == "hello"
    assert response.stop_reason in {"end_turn", "max_tokens", "tool_use", "stop_sequence"}
    assert response.usage.input_tokens == 5
    assert response.usage.output_tokens == 3


@pytest.mark.parametrize("case", ADAPTER_CASES, ids=ADAPTER_CASE_IDS)
async def test_adapter_complete_raises_runtime_error_on_http_error(
    case: AdapterCase, mock_transport: MockTransportInstaller
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    mock_transport(handler)
    client = case.make_client()
    with pytest.raises(RuntimeError):
        await client.complete(CompletionRequest(messages=[Message(role="user", content="hi")]))


@pytest.mark.parametrize("case", ADAPTER_CASES, ids=ADAPTER_CASE_IDS)
async def test_adapter_stream_terminal_chunk_is_done(
    case: AdapterCase, mock_transport: MockTransportInstaller
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    mock_transport(handler)
    client = case.make_client()
    chunks = [
        chunk
        async for chunk in client.stream(
            CompletionRequest(messages=[Message(role="user", content="hi")])
        )
    ]
    assert len(chunks) >= 1
    assert chunks[-1].done is True
