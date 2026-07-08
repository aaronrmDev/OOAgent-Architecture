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
