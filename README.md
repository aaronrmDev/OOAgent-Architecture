# OOAgent — Object-Oriented AI Agent Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](https://www.python.org/)

> A composition framework for building type-safe, provider-portable AI agents — with validation, testability, and observability wired into every turn as first-class extension points, not optional add-ons.

---

## What OOAgent Is

Every response is the return value of a deterministic method call on an instantiated class — never ad-hoc generation. The core is agnostic to both **inference backend** (Claude, GPT-4o, Gemini, Llama, Mistral, Ollama) and **problem domain** (engineering, finance, medicine, legal, etc.), both injected at construction time through stable interfaces.

## Who It's For

App teams building production agents who want architectural discipline, provider portability, and testability without hand-rolling it. (Framework authors extending OOAgent and researchers prototyping agent architectures are also served — but production app teams are who the golden path below is written for.)

## What It's Not

- Not a chat UI
- Not a low-code/visual workflow builder
- Not an autonomous, unsupervised agent runner — the FSM is turn-based and gate-enforced ([CLAUDE.md §10-12](CLAUDE.md)), not a free-running loop
- Not a prompt-template library

---

## Golden Path

```bash
uv sync --extra dev --extra otel
uv run python -m examples.minimal_agent
```

```
format:  text
content: Hello! I'm a validated OOAgent response.
```

That's a complete turn through OOAgent's FSM (`IDLE → GATHERING → MODELING → SOLVING → VALIDATING → DELIVERING → IDLE`) — a query in, an `Artifact` out, having passed through the same constraint-validation gate every turn does (empty by default here; domain contexts declare real invariants — see `examples/domain_context_agent.py`). No API key needed: this example uses a deterministic stand-in client so you can see it work before wiring a real backend.

Four focused examples, one concept each, each a complete runnable file:

| Example | Demonstrates |
|---|---|
| [`examples/minimal_agent.py`](examples/minimal_agent.py) | The smallest possible agent |
| [`examples/tool_enabled_agent.py`](examples/tool_enabled_agent.py) | Registering a tool (`ToolRegistry`) |
| [`examples/domain_context_agent.py`](examples/domain_context_agent.py) | A custom `IDomainContext`, resolved by vocabulary |
| [`examples/telemetry_enabled_agent.py`](examples/telemetry_enabled_agent.py) | Observability made visible (`ConsoleTelemetry`) |

Run any of them: `uv run python -m examples.<name>`. Each file's docstring shows the one-line swap to a real `AnthropicLLMClient`/`OpenAILLMClient` for production use.

---

## Go Deeper

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — composition root, design patterns, project structure, extension protocol
- [`docs/PUBLIC_API.md`](docs/PUBLIC_API.md) — what's core vs. advanced, and the stability contract
- [`docs/TESTING.md`](docs/TESTING.md) — how to test adapters without network calls, test doubles, coverage floor
- [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md) — event schema, failure taxonomy, wiring a telemetry backend, policy hooks and redaction
- [`docs/EXTENDING.md`](docs/EXTENDING.md) — worked examples for adding a domain context, LLM adapter, tool, or plugin
- [`docs/MCP.md`](docs/MCP.md) — run OOAgent as a host-agnostic MCP plugin (Claude Code, and any other MCP-compliant host)
- [`docs/adr/`](docs/adr/0000-template.md) — architecture decision records: why the composition root, why SpecDrivenWorkflow is a peer layer, why the curated public API barrel
- [`CLAUDE.md`](CLAUDE.md) — the full architectural contract: invariants, FSM, failure modes, testing contracts
- [`CONTRIBUTORS.md`](CONTRIBUTORS.md) — how to contribute

---

## Supported LLM Backends

| Backend   | Class                  | Notes                       |
|-----------|------------------------|-----------------------------|
| Anthropic | `AnthropicLLMClient`   | Claude 3/4 family           |
| OpenAI    | `OpenAILLMClient`      | GPT-4o, o-series            |
| Gemini    | `GeminiLLMClient`      | Gemini 1.5 / 2.0            |
| Ollama    | `OllamaLLMClient`      | Local models (Llama, Mistral, etc.) |

All backends implement `ILLMClient`. Swap them at construction — zero changes to core.

---

## Testing

```bash
uv run pytest         # run the pytest suite (pytest-asyncio, auto mode)
uv run mypy --strict  # strict type check
```

The `tests/` tree ships `StubLLMClient`, `NullTelemetry`, `NullContext`, and fixture factories for deterministic unit tests. Every `IAgent`, `IDomainContext`, `ITool`, `IPlugin`, and `ILLMClient` implementation must include a conformance test suite (see [CLAUDE.md §17](CLAUDE.md), and `tests/conformance/`).

---

## Scripts

| Command | Action |
|---|---|
| `uv sync --extra dev --extra otel` | Install runtime + dev + OpenTelemetry dependencies |
| `uv run mypy --strict` | Strict type check, no emit |
| `uv run ruff check` | Lint (import order, unused imports, upgrades) |
| `uv run pytest` | Run the test suite |
| `bash scripts/ai-safety-gate.sh --verbose` | Run the 13 AI Safety Guards |
| `bash scripts/conformance-check.sh` | Verify §17 conformance suites exist and pass |

---

## License

MIT — Copyright © 2026 OOAgent Contributors.
