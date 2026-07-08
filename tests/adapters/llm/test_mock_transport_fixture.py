"""tests/adapters/llm/test_mock_transport_fixture.py — proves the shared
mock_transport fixture actually intercepts an adapter's real HTTP call,
before other test files in this package build on it.
"""

from __future__ import annotations

import httpx

from ooagent.core.protocols import CompletionRequest, Message

from .conftest import ADAPTER_CASES, MockTransportInstaller


async def test_mock_transport_intercepts_anthropic_complete_call(
    mock_transport: MockTransportInstaller,
) -> None:
    case = next(c for c in ADAPTER_CASES if c.name == "anthropic")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=case.success_body)

    mock_transport(handler)
    client = case.make_client()
    response = await client.complete(
        CompletionRequest(messages=[Message(role="user", content="hi")])
    )
    assert response.content == "hello"
