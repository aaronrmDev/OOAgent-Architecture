# Testing & Reliability Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** replace ~49% import-only coverage on the 4 LLM adapters + Proxy classes with real behavior-matrix tests that exercise each adapter's actual `complete()`/`stream()` code paths end-to-end, using a validated zero-dependency mock-transport technique, plus a `docs/TESTING.md` writing down the pattern.

**Architecture:** a new `tests/adapters/llm/` subpackage. `conftest.py` holds a `mock_transport` fixture (monkeypatches `httpx.AsyncClient.__init__` to auto-inject `httpx.MockTransport` — validated working for both `complete()` and `stream()` during brainstorming, zero adapter code changes, zero new dependencies) plus shared per-vendor mock-response builders and an `ADAPTER_CASES` list used by both the uniform behavior-matrix tests and the documented-divergence tests. `tests/adapters/test_llm_adapters.py`'s existing 6 tests are untouched.

**Tech Stack:** Python 3.11, existing `httpx`/`pytest`/`pytest-asyncio` — no new dependencies.

## Global Constraints

- Full design: `docs/superpowers/specs/2026-07-06-testing-reliability-depth-design.md`.
- No changes to `src/ooagent/adapters/llm/*.py` — every adapter's behavior (including the two documented inconsistencies below) is read, tested, and left exactly as-is.
- No changes to `tests/adapters/test_llm_adapters.py` — purely additive work under a new `tests/adapters/llm/` subpackage.
- No new dependencies added to `pyproject.toml`.
- The two documented inconsistencies (verified during brainstorming by reading each adapter's source directly):
  1. **Token-limit pre-check**: Anthropic, OpenAI, and Gemini raise `TokenLimitError` before any HTTP call when the client-side token estimate exceeds `max_tokens`. Ollama has no such check.
  2. **Empty-response handling**: OpenAI and Ollama raise `RuntimeError("... returned no choices")` when the response has no completions. Anthropic and Gemini silently return `CompletionResponse(content="")` instead.
- Per-vendor mock success-response JSON shapes (confirmed from each adapter's `_parse()` method — use these exact shapes, not approximations):
  ```
  Anthropic: {"content": [{"type": "text", "text": "..."}], "stop_reason": "end_turn", "usage": {"input_tokens": N, "output_tokens": N}}
  OpenAI:    {"choices": [{"message": {"content": "..."}, "finish_reason": "stop"}], "usage": {"prompt_tokens": N, "completion_tokens": N}}
  Gemini:    {"candidates": [{"content": {"parts": [{"text": "..."}]}, "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": N, "candidatesTokenCount": N}}
  Ollama:    {"choices": [{"message": {"content": "..."}, "finish_reason": "stop"}], "usage": {"prompt_tokens": N, "completion_tokens": N}}
  ```
- Run `PYTHONPATH=src uv run pytest tests/ -q` after every task to confirm the full suite (old + new) stays green.
- Every task's final verification step includes `uv run ruff check && uv run ruff format --check && uv run mypy --strict` — the mock-transport fixture's typing (`Any` for the patched `__init__`'s `*args`/`**kwargs`) was verified clean under `mypy --strict` during brainstorming; use that exact typing, not a stricter alternative that will fail.

---

### Task 1: `tests/adapters/llm/conftest.py` — mock-transport fixture + shared adapter test data

**Files:**
- Create: `tests/adapters/llm/__init__.py`
- Create: `tests/adapters/llm/conftest.py`
- Create: `tests/adapters/llm/test_mock_transport_fixture.py`

**Interfaces:**
- Consumes: `AnthropicConfig`/`AnthropicLLMClient`, `OpenAIConfig`/`OpenAILLMClient`, `GeminiConfig`/`GeminiLLMClient`, `OllamaConfig`/`OllamaLLMClient` (all pre-existing, unchanged); `ILLMClient`, `LLMVendor`, `CompletionRequest`, `Message` (`ooagent.core.protocols`, pre-existing).
- Produces: `mock_transport` fixture (auto-injected by pytest, no import needed to use it — only its type `MockTransportInstaller` needs importing for annotations); `anthropic_success_body`/`openai_success_body`/`gemini_success_body`/`ollama_success_body` functions; `AdapterCase` dataclass; `ADAPTER_CASES: list[AdapterCase]`; `ADAPTER_CASE_IDS: list[str]` — all consumed by Tasks 2 and 3.

- [ ] **Step 1: Write the failing test**

Create `tests/adapters/llm/__init__.py`:

```python
```

(empty file — marks the test package, matching `tests/adapters/__init__.py`'s pattern)

Create `tests/adapters/llm/test_mock_transport_fixture.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src uv run pytest tests/adapters/llm/test_mock_transport_fixture.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.adapters.llm.conftest'`

- [ ] **Step 3: Write the implementation**

Create `tests/adapters/llm/conftest.py`:

```python
"""tests/adapters/llm/conftest.py — shared fixtures and test data for LLM adapter tests.

Each adapter constructs httpx.AsyncClient() fresh per call rather than
accepting an injected client, so the standard "pass a client with a
MockTransport" pattern doesn't apply directly. mock_transport instead
monkeypatches httpx.AsyncClient.__init__ for the duration of a test so
any internally-constructed client automatically uses a MockTransport —
no adapter code changes needed, no new dependency, no real network access.

ADAPTER_CASES is the shared behavior-matrix fixture data: one AdapterCase
per real LLM adapter, reused by both test_behavior_matrix.py (uniform
assertions) and test_adapter_specific_behaviors.py (documented per-adapter
divergences — see docs/TESTING.md "Known Gaps").
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from ooagent.adapters.llm.anthropic import AnthropicConfig, AnthropicLLMClient
from ooagent.adapters.llm.gemini import GeminiConfig, GeminiLLMClient
from ooagent.adapters.llm.ollama import OllamaConfig, OllamaLLMClient
from ooagent.adapters.llm.openai import OpenAIConfig, OpenAILLMClient
from ooagent.core.protocols import ILLMClient, LLMVendor

MockHandler = Callable[[httpx.Request], httpx.Response]
MockTransportInstaller = Callable[[MockHandler], None]


@pytest.fixture
def mock_transport(monkeypatch: pytest.MonkeyPatch) -> MockTransportInstaller:
    original_init = httpx.AsyncClient.__init__

    def install(handler: MockHandler) -> None:
        def patched_init(self: httpx.AsyncClient, *args: Any, **kwargs: Any) -> None:
            kwargs.setdefault("transport", httpx.MockTransport(handler))
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    return install


def anthropic_success_body(text: str = "hello") -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 5, "output_tokens": 3},
    }


def openai_success_body(text: str = "hello") -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }


def gemini_success_body(text: str = "hello") -> dict[str, Any]:
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 3},
    }


def ollama_success_body(text: str = "hello") -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }


@dataclass(frozen=True)
class AdapterCase:
    name: str
    vendor: LLMVendor
    make_client: Callable[[], ILLMClient]
    make_client_with_max_tokens: Callable[[int], ILLMClient]
    success_body: dict[str, Any]


ADAPTER_CASES: list[AdapterCase] = [
    AdapterCase(
        name="anthropic",
        vendor="anthropic",
        make_client=lambda: AnthropicLLMClient(AnthropicConfig(api_key="key")),
        make_client_with_max_tokens=lambda mt: AnthropicLLMClient(
            AnthropicConfig(api_key="key", max_tokens=mt)
        ),
        success_body=anthropic_success_body("hello"),
    ),
    AdapterCase(
        name="openai",
        vendor="openai",
        make_client=lambda: OpenAILLMClient(OpenAIConfig(api_key="key")),
        make_client_with_max_tokens=lambda mt: OpenAILLMClient(
            OpenAIConfig(api_key="key", max_tokens=mt)
        ),
        success_body=openai_success_body("hello"),
    ),
    AdapterCase(
        name="gemini",
        vendor="gemini",
        make_client=lambda: GeminiLLMClient(GeminiConfig(api_key="key")),
        make_client_with_max_tokens=lambda mt: GeminiLLMClient(
            GeminiConfig(api_key="key", max_tokens=mt)
        ),
        success_body=gemini_success_body("hello"),
    ),
    AdapterCase(
        name="ollama",
        vendor="ollama",
        make_client=lambda: OllamaLLMClient(OllamaConfig()),
        make_client_with_max_tokens=lambda mt: OllamaLLMClient(OllamaConfig(max_tokens=mt)),
        success_body=ollama_success_body("hello"),
    ),
]

ADAPTER_CASE_IDS: list[str] = [c.name for c in ADAPTER_CASES]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/adapters/llm/test_mock_transport_fixture.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite, type-check, lint, and commit**

Run: `PYTHONPATH=src uv run pytest tests/ -q`
Expected: all tests pass (old + 1 new)

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check`
Expected: mypy clean, ruff clean

```bash
git add tests/adapters/llm/__init__.py tests/adapters/llm/conftest.py tests/adapters/llm/test_mock_transport_fixture.py
git commit -m "test(adapters): add mock-transport fixture + shared adapter test data"
```

---

### Task 2: `tests/adapters/llm/test_behavior_matrix.py` — uniform cross-adapter contract

**Files:**
- Create: `tests/adapters/llm/test_behavior_matrix.py`

**Interfaces:**
- Consumes: `ADAPTER_CASES`, `ADAPTER_CASE_IDS`, `AdapterCase`, `MockTransportInstaller` (Task 1's `conftest.py`).
- Produces: nothing consumed by other tasks — this is a leaf test file.

- [ ] **Step 1: Write the test**

Create `tests/adapters/llm/test_behavior_matrix.py`:

```python
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
        await client.complete(
            CompletionRequest(messages=[Message(role="user", content="hi")])
        )


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
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/adapters/llm/test_behavior_matrix.py -v`
Expected: PASS (24 tests — 6 assertions x 4 adapters)

- [ ] **Step 3: Run the full suite, type-check, lint, and commit**

Run: `PYTHONPATH=src uv run pytest tests/ -q`
Expected: all tests pass (old + 24 new)

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check`
Expected: mypy clean, ruff clean

```bash
git add tests/adapters/llm/test_behavior_matrix.py
git commit -m "test(adapters): add cross-adapter behavior-matrix test suite"
```

---

### Task 3: `tests/adapters/llm/test_adapter_specific_behaviors.py` — documented divergences

**Files:**
- Create: `tests/adapters/llm/test_adapter_specific_behaviors.py`

**Interfaces:**
- Consumes: `ADAPTER_CASES`, `AdapterCase`, `MockTransportInstaller` (Task 1's `conftest.py`).
- Produces: nothing consumed by other tasks — leaf test file.

- [ ] **Step 1: Write the test**

Create `tests/adapters/llm/test_adapter_specific_behaviors.py`:

```python
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
        await client.complete(
            CompletionRequest(messages=[Message(role="user", content="hi")])
        )


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
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/adapters/llm/test_adapter_specific_behaviors.py -v`
Expected: PASS (8 tests: 3 token-limit-checked + 1 ollama-no-precheck + 2 raises-on-empty + 2 defaults-to-empty)

- [ ] **Step 3: Run the full suite, type-check, lint, and commit**

Run: `PYTHONPATH=src uv run pytest tests/ -q`
Expected: all tests pass (old + 8 new)

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check`
Expected: mypy clean, ruff clean

```bash
git add tests/adapters/llm/test_adapter_specific_behaviors.py
git commit -m "test(adapters): document and test the 2 real cross-adapter behavior divergences"
```

---

### Task 4: `tests/adapters/llm/test_throttling_proxy.py` — ThrottlingLLMProxy (zero prior coverage)

**Files:**
- Create: `tests/adapters/llm/test_throttling_proxy.py`

**Interfaces:**
- Consumes: `ThrottlingLLMProxy`, `ThrottlingOptions` (`ooagent.adapters.llm.caching_proxy`, pre-existing, unchanged); `ILLMClient`, `LLMVendor`, `CompletionChunk`, `CompletionRequest`, `CompletionResponse`, `Message`, `TokenUsage` (`ooagent.core.protocols`, pre-existing).
- Produces: nothing consumed by other tasks — leaf test file.

- [ ] **Step 1: Write the test**

Create `tests/adapters/llm/test_throttling_proxy.py`:

```python
"""tests/adapters/llm/test_throttling_proxy.py — ThrottlingLLMProxy (zero prior coverage)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from ooagent.adapters.llm.caching_proxy import ThrottlingLLMProxy, ThrottlingOptions
from ooagent.core.protocols import (
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    ILLMClient,
    LLMVendor,
    Message,
    TokenUsage,
)


class _StubInnerClient(ILLMClient):
    def __init__(self) -> None:
        self.complete_calls = 0
        self.stream_calls = 0

    @property
    def vendor(self) -> LLMVendor:
        return "anthropic"

    @property
    def model_id(self) -> str:
        return "stub-model"

    @property
    def max_tokens(self) -> int:
        return 4096

    @property
    def supports_tools(self) -> bool:
        return False

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.complete_calls += 1
        return CompletionResponse(
            content="stub response",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        self.stream_calls += 1
        yield CompletionChunk(delta="stub", done=False)
        yield CompletionChunk(delta="", done=True)


def test_throttling_proxy_delegates_vendor_and_config_properties_to_inner() -> None:
    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    assert proxy.vendor == inner.vendor
    assert proxy.model_id == inner.model_id
    assert proxy.max_tokens == inner.max_tokens
    assert proxy.supports_tools == inner.supports_tools


async def test_throttling_proxy_complete_delegates_to_inner_client() -> None:
    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    response = await proxy.complete(
        CompletionRequest(messages=[Message(role="user", content="hi")])
    )
    assert response.content == "stub response"
    assert inner.complete_calls == 1


async def test_throttling_proxy_stream_delegates_to_inner_client() -> None:
    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    chunks = [
        chunk
        async for chunk in proxy.stream(
            CompletionRequest(messages=[Message(role="user", content="hi")])
        )
    ]
    assert chunks[-1].done is True
    assert inner.stream_calls == 1


async def test_throttling_proxy_does_not_sleep_when_tokens_available() -> None:
    """A fresh proxy starts with a full token bucket (_tokens ==
    requests_per_minute) — a single request must not trigger the
    sleep-based throttle path in _throttle()."""
    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    start = time.monotonic()
    await proxy.complete(CompletionRequest(messages=[Message(role="user", content="hi")]))
    elapsed = time.monotonic() - start
    assert elapsed < 0.5


def test_refill_replenishes_tokens_proportional_to_elapsed_time() -> None:
    """White-box test of _refill()'s token-bucket math, asserted directly
    against internal state rather than by actually sleeping — keeps this
    test fast and deterministic (CLAUDE.md §17)."""
    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    proxy._tokens = 0  # type: ignore[attr-defined]
    proxy._last_refill -= 30.0  # type: ignore[attr-defined]  # simulate 30s elapsed
    proxy._refill()  # type: ignore[attr-defined]
    # 60 requests/minute * (30s / 60s) = 30 tokens refilled
    assert proxy._tokens == 30  # type: ignore[attr-defined]


def test_refill_caps_tokens_at_requests_per_minute() -> None:
    inner = _StubInnerClient()
    proxy = ThrottlingLLMProxy(inner, ThrottlingOptions(requests_per_minute=60))
    proxy._tokens = 50  # type: ignore[attr-defined]
    proxy._last_refill -= 120.0  # type: ignore[attr-defined]  # simulate 2 minutes elapsed
    proxy._refill()  # type: ignore[attr-defined]
    assert proxy._tokens == 60  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/adapters/llm/test_throttling_proxy.py -v`
Expected: PASS (6 tests)

- [ ] **Step 3: Run the full suite, type-check, lint, and commit**

Run: `PYTHONPATH=src uv run pytest tests/ -q`
Expected: all tests pass (old + 6 new)

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check`
Expected: mypy clean, ruff clean (the `# type: ignore[attr-defined]` comments on the two white-box `_refill`/`_tokens`/`_last_refill` tests are expected and correct — `mypy --strict` would otherwise reject direct access to `ThrottlingLLMProxy`'s private attributes from outside the class)

```bash
git add tests/adapters/llm/test_throttling_proxy.py
git commit -m "test(adapters): add ThrottlingLLMProxy tests (zero prior coverage)"
```

---

### Task 5: `docs/TESTING.md` + README link

**Files:**
- Create: `docs/TESTING.md`
- Modify: `README.md` (append one line to the existing "Go Deeper" list)

**Interfaces:**
- Consumes: the mock-transport pattern and the two documented inconsistencies from Tasks 1–3 (described here, not re-implemented).
- Produces: nothing consumed by other tasks — final task.

- [ ] **Step 1: Create `docs/TESTING.md`**

Create `docs/TESTING.md`:

```markdown
# Testing Strategy

## Testing LLM adapters without network calls

Each adapter (`AnthropicLLMClient`, `OpenAILLMClient`, `GeminiLLMClient`,
`OllamaLLMClient`) constructs `httpx.AsyncClient()` fresh per call rather
than accepting an injected client, so the usual "pass a client configured
with `httpx.MockTransport`" pattern doesn't apply directly.

`tests/adapters/llm/conftest.py`'s `mock_transport` fixture solves this
by monkeypatching `httpx.AsyncClient.__init__` for the duration of a
test, so any internally-constructed client automatically gets a
`MockTransport` — no adapter code changes, no new dependency, no real
network access. Use it whenever you need to exercise an adapter's real
`complete()`/`stream()` code path (not just its private `_build_body()`/
`_parse()` methods in isolation):

```python
async def test_something(mock_transport: MockTransportInstaller) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={...})

    mock_transport(handler)
    client = AnthropicLLMClient(AnthropicConfig(api_key="key"))
    response = await client.complete(...)
```

`tests/adapters/llm/conftest.py` also exports `ADAPTER_CASES` — one
`AdapterCase` per real adapter, with a `make_client()` factory and a
correct mock success-response body per vendor. Reuse it for any new
cross-adapter test rather than hand-rolling adapter construction.

## Test doubles

- **`StubLLMClient`** (`tests/stub_llm_client.py`) — a fully scripted,
  deterministic `ILLMClient` for tests that need an agent to actually
  complete a turn (not adapter-level HTTP behavior). Script responses by
  message-content pattern.
- **`NullContext`** (`src/ooagent/contexts/null_context.py`) — the
  built-in safe-default `IDomainContext`; use as the baseline for
  agent-level tests that don't need a real domain.
- **`NullTelemetry`** (`src/ooagent/telemetry/null_telemetry.py`) — a
  no-op `ITelemetryProvider`; the default for tests that don't assert on
  telemetry output.

## Coverage floor

70%, enforced by `.specify/gates/Makefile`'s `coverage-gate` target
(`pytest --cov-fail-under=70`). See [CLAUDE.md §17](../CLAUDE.md) for
what conformance suites must verify, and
[docs/SPECDRIVEN.md](SPECDRIVEN.md) for why 70% and how it ratchets
upward over time (Article VII, "Zero Defects").

## Known gaps

Two real behavior differences between the LLM adapters, discovered and
tested-as-is (not fixed) while building the behavior-matrix suite —
deliberate current state, not oversights:

1. **Token-limit pre-check**: Anthropic, OpenAI, and Gemini raise
   `TokenLimitError` before any HTTP call when the client-side token
   estimate exceeds `max_tokens`. **Ollama has no such check** — an
   oversized request reaches the HTTP layer unchecked. See
   `tests/adapters/llm/test_adapter_specific_behaviors.py::test_ollama_has_no_client_side_token_limit_precheck`.
2. **Empty-response handling**: a response with zero choices/candidates
   causes OpenAI and Ollama to raise `RuntimeError("... returned no
   choices")`, while Anthropic and Gemini silently return
   `content=""`. See
   `tests/adapters/llm/test_adapter_specific_behaviors.py::test_empty_choices_raises_runtime_error`
   and `::test_empty_content_defaults_to_empty_string_without_raising`.

Fixing either is a deliberate future decision (normalizing adapter
behavior is itself a design choice — silently "fixing" one direction or
the other without deciding which behavior is correct isn't done here).
```

- [ ] **Step 2: Add the README link**

In `README.md`, find this exact text:

```
## Go Deeper

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — composition root, design patterns, project structure, extension protocol
- [`docs/PUBLIC_API.md`](docs/PUBLIC_API.md) — what's core vs. advanced, and the stability contract
- [`CLAUDE.md`](CLAUDE.md) — the full architectural contract: invariants, FSM, failure modes, testing contracts
- [`CONTRIBUTORS.md`](CONTRIBUTORS.md) — how to contribute
```

Replace it with:

```
## Go Deeper

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — composition root, design patterns, project structure, extension protocol
- [`docs/PUBLIC_API.md`](docs/PUBLIC_API.md) — what's core vs. advanced, and the stability contract
- [`docs/TESTING.md`](docs/TESTING.md) — how to test adapters without network calls, test doubles, coverage floor
- [`CLAUDE.md`](CLAUDE.md) — the full architectural contract: invariants, FSM, failure modes, testing contracts
- [`CONTRIBUTORS.md`](CONTRIBUTORS.md) — how to contribute
```

- [ ] **Step 3: Confirm links resolve**

Run: `test -f docs/ARCHITECTURE.md && test -f docs/PUBLIC_API.md && test -f docs/TESTING.md && test -f CLAUDE.md && test -f docs/SPECDRIVEN.md && echo "all targets exist"`
Expected: `all targets exist`

- [ ] **Step 4: Run the full verification suite**

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check && PYTHONPATH=src uv run pytest tests/ --cov=ooagent.adapters.llm --cov-report=term-missing -q`
Expected: all pass — 0 mypy errors, 0 ruff findings, full test suite green (old + 39 new from Tasks 1-4), and `src/ooagent/adapters/llm/` coverage visibly higher than the ~49% baseline measured during brainstorming (method bodies are now actually exercised, not just imported)

- [ ] **Step 5: Commit**

```bash
git add docs/TESTING.md README.md
git commit -m "docs: add TESTING.md — mock-transport pattern, test doubles, known gaps"
```

---

## Final Verification (before finishing-a-development-branch)

After Task 5, confirm the whole branch is coherent:

```bash
uv run mypy --strict
uv run ruff check
uv run ruff format --check
PYTHONPATH=src uv run pytest tests/ --cov=ooagent.adapters.llm --cov-report=term-missing -q
PYTHONPATH=src uv run pytest tests/ -q
```

All must exit 0. `git diff --stat` against the branch's base should show
only: `tests/adapters/llm/` (6 new files: `__init__.py`, `conftest.py`,
`test_mock_transport_fixture.py`, `test_behavior_matrix.py`,
`test_adapter_specific_behaviors.py`, `test_throttling_proxy.py`),
`docs/TESTING.md` (new), `README.md` (one line added). No file under
`src/ooagent/adapters/llm/` or `tests/adapters/test_llm_adapters.py`
should appear.
