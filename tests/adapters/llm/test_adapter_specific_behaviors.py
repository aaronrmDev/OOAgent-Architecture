"""tests/adapters/llm/test_adapter_specific_behaviors.py — documented
per-adapter behavior divergences (not bugs — see docs/TESTING.md
"Known Gaps"). These are deliberately NOT part of the uniform behavior
matrix (test_behavior_matrix.py) because the 4 real adapters genuinely
disagree here, confirmed by reading each adapter's source directly.
"""

from __future__ import annotations

import httpx
import pytest

from ooagent.core.protocols import CompletionRequest, Message, TokenLimitError

from .conftest import ADAPTER_CASES, AdapterCase, MockTransportInstaller

_TOKEN_LIMIT_CHECKED = [c for c in ADAPTER_CASES if c.name != "ollama"]
_TOKEN_LIMIT_CHECKED_IDS = [c.name for c in _TOKEN_LIMIT_CHECKED]

_RAISES_ON_EMPTY = [c for c in ADAPTER_CASES if c.name in {"openai", "ollama"}]
_RAISES_ON_EMPTY_IDS = [c.name for c in _RAISES_ON_EMPTY]

_DEFAULTS_TO_EMPTY = [c for c in ADAPTER_CASES if c.name in {"anthropic", "gemini"}]
_DEFAULTS_TO_EMPTY_IDS = [c.name for c in _DEFAULTS_TO_EMPTY]


@pytest.mark.parametrize("case", _TOKEN_LIMIT_CHECKED, ids=_TOKEN_LIMIT_CHECKED_IDS)
async def test_client_side_token_limit_precheck_raises_before_any_http_call(
    case: AdapterCase,
) -> None:
    """Anthropic, OpenAI, and Gemini estimate tokens client-side and raise
    TokenLimitError before ever making an HTTP call — no mock_transport
    fixture needed here, since a real network call would be a test bug
    if this assertion holds."""
    client = case.make_client_with_max_tokens(1)
    request = CompletionRequest(messages=[Message(role="user", content="x" * 100)])
    with pytest.raises(TokenLimitError):
        await client.complete(request)


async def test_ollama_has_no_client_side_token_limit_precheck(
    mock_transport: MockTransportInstaller,
) -> None:
    """Documented gap (docs/TESTING.md): unlike the other 3 adapters,
    Ollama does not estimate tokens client-side before the HTTP call —
    an oversized request reaches the (mocked) HTTP layer instead of
    raising TokenLimitError locally."""
    case = next(c for c in ADAPTER_CASES if c.name == "ollama")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=case.success_body)

    mock_transport(handler)
    client = case.make_client_with_max_tokens(1)
    request = CompletionRequest(messages=[Message(role="user", content="x" * 100)])
    response = await client.complete(request)
    assert response.content == "hello"


@pytest.mark.parametrize("case", _RAISES_ON_EMPTY, ids=_RAISES_ON_EMPTY_IDS)
async def test_empty_choices_raises_runtime_error(
    case: AdapterCase, mock_transport: MockTransportInstaller
) -> None:
    """OpenAI and Ollama raise RuntimeError("... returned no choices")
    when the response has zero choices."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    mock_transport(handler)
    client = case.make_client()
    with pytest.raises(RuntimeError, match="no choices"):
        await client.complete(CompletionRequest(messages=[Message(role="user", content="hi")]))


@pytest.mark.parametrize("case", _DEFAULTS_TO_EMPTY, ids=_DEFAULTS_TO_EMPTY_IDS)
async def test_empty_content_defaults_to_empty_string_without_raising(
    case: AdapterCase, mock_transport: MockTransportInstaller
) -> None:
    """Anthropic and Gemini do NOT raise when the response has no
    content blocks / candidates — they silently return content=''."""
    empty_body: dict[str, object] = (
        {"content": []} if case.name == "anthropic" else {"candidates": []}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=empty_body)

    mock_transport(handler)
    client = case.make_client()
    response = await client.complete(
        CompletionRequest(messages=[Message(role="user", content="hi")])
    )
    assert response.content == ""
