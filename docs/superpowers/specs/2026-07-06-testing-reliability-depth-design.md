# Testing & Reliability Depth — Design

## Purpose

Sub-project C of the OOAgent improvement backlog (A: golden path,
shipped PR #8; B: public API, shipped PR #9). The original proposal
asked for behavior-matrix tests across LLM adapters, property-based
tests, failure-mode tests, and a documented test strategy. Investigation
found the single biggest concrete gap: the 4 LLM adapters
(`anthropic.py`, `openai.py`, `gemini.py`, `ollama.py`) plus
`caching_proxy.py`'s two Proxy classes have only 6 shallow tests total,
~49% coverage that is mostly *import-only* (class/method definitions
count as covered from being imported; method bodies — request-building,
HTTP-error handling, response-parsing — are almost never actually
executed by a test). `ThrottlingLLMProxy` has zero tests.

**Goal:** a shared, reusable mock-transport testing pattern that
exercises each adapter's real `complete()`/`stream()` code paths
end-to-end (not just private `_build_body()`/`_parse()` methods in
isolation, which is all the existing 6 tests do), applied as a
parametrized behavior matrix across all 4 adapters where their contract
is uniform, plus documented per-adapter tests where two real
inconsistencies were found — and a `docs/TESTING.md` that writes down
the pattern so future adapter/tool authors don't have to rediscover it.

## Scope

**In scope:**

1. `tests/adapters/llm/conftest.py` — a fixture that monkeypatches
   `httpx.AsyncClient.__init__` to auto-inject an `httpx.MockTransport`,
   validated working end-to-end during brainstorming (real `complete()`
   call intercepted, zero network access, no new dependency).
2. `tests/adapters/llm/test_behavior_matrix.py` — parametrized tests
   asserting properties that hold uniformly across all 4 real adapters.
3. `tests/adapters/llm/test_adapter_specific_behaviors.py` — the two
   confirmed real inconsistencies (below), tested per-adapter and
   explicitly commented as documented, not accidental.
4. `tests/adapters/llm/test_throttling_proxy.py` — new tests for
   `ThrottlingLLMProxy` (zero existing coverage).
5. `docs/TESTING.md` + one new line in README's "Go Deeper" list.

**Out of scope** (per brainstorming discussion):

- Property-based testing (`hypothesis`) — a new dependency and a new
  testing paradigm for this repo; deferred, not part of this pass.
- Mutation testing (`mutmut`/similar) — same reasoning.
- **Fixing** the two discovered adapter inconsistencies (Ollama's
  missing token-limit pre-check; Anthropic/Gemini silently defaulting
  empty content vs. OpenAI/Ollama raising `RuntimeError` on no-choices)
  — this pass documents and tests current behavior as-is; changing
  adapter behavior is a separate, later decision.
- Modifying `tests/adapters/test_llm_adapters.py`'s existing 6 tests —
  they remain valid and untouched; this is purely additive.

## The mock-transport fixture (validated)

```python
import httpx
import pytest
from collections.abc import Callable

@pytest.fixture
def mock_transport(monkeypatch: pytest.MonkeyPatch) -> Callable[[Callable[[httpx.Request], httpx.Response]], None]:
    """Auto-inject an httpx.MockTransport into every httpx.AsyncClient()
    constructed for the duration of the test, so adapters' real
    complete()/stream() code paths run against a deterministic fake
    HTTP layer instead of the network — no adapter code changes needed."""
    original_init = httpx.AsyncClient.__init__

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> None:
        def patched_init(self: httpx.AsyncClient, *args: object, **kwargs: object) -> None:
            kwargs.setdefault("transport", httpx.MockTransport(handler))
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    return install
```

Confirmed working during brainstorming: constructing `AnthropicLLMClient`
and calling `await client.complete(request)` against a handler returning
a mocked 200 JSON body round-trips through the adapter's real HTTP call
and JSON parsing into a correct `CompletionResponse` — zero network
access.

## Behavior matrix (uniform across all 4 real adapters)

- `vendor` matches the expected `LLMVendor` literal per adapter.
- `model_id` and `max_tokens` default to non-empty/positive values when
  config omits them.
- A mocked 200 response with a vendor-appropriate success body round-trips
  through the real `complete()` into a `CompletionResponse` with
  non-empty `content`, a valid `stop_reason`, and populated `usage`.
- A mocked 4xx or 5xx response raises `RuntimeError` from `complete()`
  (confirmed identical across all 4: `f"{Vendor} API error: {status} ..."`).
- `stream()`'s final yielded `CompletionChunk` has `done=True`.

Per-vendor mock success response shapes (confirmed by reading each
adapter's `_parse()`):

```
Anthropic: {"content": [{"type": "text", "text": "..."}], "stop_reason": "end_turn", "usage": {"input_tokens": N, "output_tokens": N}}
OpenAI:    {"choices": [{"message": {"content": "..."}, "finish_reason": "stop"}], "usage": {"prompt_tokens": N, "completion_tokens": N}}
Gemini:    {"candidates": [{"content": {"parts": [{"text": "..."}]}, "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": N, "candidatesTokenCount": N}}
Ollama:    {"choices": [{"message": {"content": "..."}, "finish_reason": "stop"}], "usage": {"prompt_tokens": N, "completion_tokens": N}}
```

## Documented per-adapter inconsistencies (not fixed, tested as-is)

1. **Token-limit pre-check**: Anthropic, OpenAI, and Gemini all raise
   `TokenLimitError` before making the HTTP call when the client-side
   token estimate exceeds `max_tokens` (an existing test already covers
   Anthropic's case; this pass adds OpenAI and Gemini). **Ollama has no
   such check** — an oversized request reaches the HTTP layer
   unchecked. Tested via `@pytest.mark.parametrize` over exactly
   `[Anthropic, OpenAI, Gemini]`, with a sibling
   `test_ollama_has_no_token_limit_precheck` documenting the absence
   explicitly (asserts the request is NOT rejected client-side).
2. **Empty-response handling**: a mocked response with zero
   choices/candidates causes OpenAI and Ollama to raise
   `RuntimeError("... returned no choices")`, while Anthropic and Gemini
   silently return a `CompletionResponse` with `content=""`. Tested via
   two separate parametrized groups, each asserting its own real
   behavior.

Both are called out by name in `docs/TESTING.md`'s "Known Gaps" section
so they're discoverable without reading test source.

## `ThrottlingLLMProxy` tests

Currently zero coverage. New tests: pass-through delegation (`vendor`,
`model_id`, `max_tokens`, `supports_tools`, `complete()`, `stream()` all
forward to the wrapped inner client); the token-bucket refill math in
`_refill()` (tested directly against `time.monotonic()`-independent
assertions on `_tokens`/`_last_refill` state, not by actually sleeping —
keeps the test suite fast, consistent with this repo's existing
determinism discipline per CLAUDE.md §17).

## `docs/TESTING.md` structure

```markdown
# Testing Strategy

## Testing LLM adapters without network calls
[the mock-transport fixture pattern, why it's needed (AsyncClient is
constructed fresh per call, not injected), where it lives]

## Test doubles
[StubLLMClient, NullContext, NullTelemetry — what each is for, already
existing, just documented here for the first time]

## Coverage floor
[70%, set by .specify/gates/Makefile's coverage-gate — CLAUDE.md §17 +
docs/SPECDRIVEN.md are authoritative on WHY; this doc just states the
number and points there]

## Known gaps
[the two adapter inconsistencies above, explicitly named, with a note
that fixing them is a deliberate future decision, not an oversight]
```

## Testing

Every new test file is itself tested by running (TDD: each assertion
written to fail first against the real adapter code, then verified
passing) — this sub-project's "testing" is the deliverable, not a
separate concern layered on top.

## Out-of-scope confirmation

No changes to `src/ooagent/adapters/llm/*.py` — every adapter's
behavior (including the two documented inconsistencies) is read, tested,
and left exactly as-is. No new dependencies added to `pyproject.toml`.
`tests/adapters/test_llm_adapters.py` is read but not modified.
