# Golden Path & Positioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** give OOAgent a 5-minute, zero-API-key golden path (four tiered, tested, runnable examples) and a positioning-first README, so a skeptical developer can see the framework work before reading any architecture theory.

**Architecture:** `examples/` becomes a small importable package (`examples/__init__.py`) with a shared `DemoLLMClient` (`examples/_common.py` — a deterministic `ILLMClient`, example-only scaffolding, never part of `src/ooagent/`'s public API) and four example modules, each runnable via `uv run python -m examples.<name>` and each demonstrating exactly one onboarding tier. `tests/examples/test_examples.py` imports each example's `main()` coroutine directly and asserts on its printed output via `capsys`. The current README's deep-architecture content (composition diagram, project-structure tree, FSM diagram, pattern catalog, SOLID table, extension protocol, output discipline) moves to a new `docs/ARCHITECTURE.md`; `README.md` is rewritten to lead with positioning and the golden path.

**Tech Stack:** Python 3.11, existing `ooagent` package (no new runtime dependencies), `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`, already configured — bare `async def test_...` functions need no decorator).

## Global Constraints

- Full design: `docs/superpowers/specs/2026-07-06-golden-path-examples-design.md`.
- No changes to `src/ooagent/core/`, `adapters/`, `contexts/`, `plugins/`, or `telemetry/` — every task in this plan only adds new files under `examples/`/`tests/examples/`/`docs/`, or edits `README.md`.
- `DemoLLMClient` lives in `examples/_common.py`, **not** `tests/stub_llm_client.py` — examples must be runnable standalone (`uv run python -m examples.<name>`) without pulling in the test tree, matching CLAUDE.md §7's src/tests separation.
- Every example is run via `uv run python -m examples.<name>` (module form, not `python examples/<name>.py` directly) — this is what makes `from ._common import DemoLLMClient` (a relative import) work, and what makes `import examples.<name>` work cleanly from `tests/examples/test_examples.py` without any `PYTHONPATH`/`sys.path` hacks (pytest's default import mode inserts the repo root into `sys.path` on its own once `tests/examples/__init__.py` exists, since that's the first ancestor directory without an `__init__.py`).
- Every example prints its artifact's `format` and `content` at minimum; each has a module docstring showing the one-line swap to a real `ILLMClient` (e.g. `AnthropicLLMClient`) for production use.
- `ruff check` scans the whole project by default (no path restriction in `pyproject.toml`), so `examples/`/`tests/examples/` ARE linted — every task must keep `ruff check`/`ruff format --check` clean. `mypy --strict` is configured with `packages = ["ooagent"]` in `pyproject.toml`, so it does **not** scan `examples/`/`tests/` — no mypy verification needed for this plan's new files (consistent with `tests/` already not being mypy-checked).
- Run `PYTHONPATH=src uv run pytest tests/ -q` after every task to confirm the full suite (old + new) stays green.

---

### Task 1: `examples/` package + `DemoLLMClient` + `minimal_agent.py`

**Files:**
- Create: `examples/__init__.py`
- Create: `examples/_common.py`
- Create: `examples/minimal_agent.py`
- Create: `tests/examples/__init__.py`
- Create: `tests/examples/test_examples.py`

**Interfaces:**
- Consumes: `ILLMClient`, `CompletionRequest`, `CompletionResponse`, `CompletionChunk`, `LLMVendor`, `TokenUsage` (all from `ooagent.core.protocols`); `OOAgent` (`ooagent.core.agent`); `AgentConfig`, `Query` (`ooagent.core.protocols`).
- Produces: `DemoLLMClient` class (`examples/_common.py`) — consumed by every later task's example; `main()` coroutine in `examples/minimal_agent.py` — consumed by `tests/examples/test_examples.py` (this task) and no other task.

- [ ] **Step 1: Write the failing test**

Create `tests/examples/__init__.py`:

```python
```

(empty file — marks the test package, matching `tests/core/__init__.py`'s pattern)

Create `tests/examples/test_examples.py`:

```python
"""tests/examples/test_examples.py — golden-path examples run end-to-end."""

from __future__ import annotations

import pytest

from examples.minimal_agent import main as minimal_main


async def test_minimal_agent_runs_and_prints_artifact(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await minimal_main()
    captured = capsys.readouterr()
    assert "format:  text" in captured.out
    assert "content: Hello! I'm a validated OOAgent response." in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src uv run pytest tests/examples/test_examples.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'examples'`

- [ ] **Step 3: Write the implementation**

Create `examples/__init__.py`:

```python
"""examples/__init__.py — runnable golden-path examples for OOAgent.

Each example is a complete, self-contained script demonstrating one tier
of the framework's onboarding path. Run any of them directly:

    uv run python -m examples.minimal_agent
    uv run python -m examples.tool_enabled_agent
    uv run python -m examples.domain_context_agent
    uv run python -m examples.telemetry_enabled_agent

None of these require an API key — they use DemoLLMClient
(examples/_common.py), a deterministic ILLMClient. Swap it for
ooagent.adapters.llm.anthropic.AnthropicLLMClient (or any other
ILLMClient) to talk to a real provider.
"""

from __future__ import annotations
```

Create `examples/_common.py`:

```python
"""examples/_common.py — DemoLLMClient: a deterministic ILLMClient shared
by the golden-path examples so each one runs with zero API keys and zero
network access. Not part of the installed ooagent package's public API
(src/ooagent/) — this is example-only scaffolding, the same role
tests/stub_llm_client.py plays for the test suite (CLAUDE.md §7 keeps
test/example doubles out of src/).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ooagent.core.protocols import (
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    ILLMClient,
    LLMVendor,
    TokenUsage,
)


class DemoLLMClient(ILLMClient):
    """Always returns the same scripted response — deterministic, offline."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    @property
    def model_id(self) -> str:
        return "demo-1.0"

    @property
    def vendor(self) -> LLMVendor:
        return "anthropic"

    @property
    def max_tokens(self) -> int:
        return 4096

    @property
    def supports_tools(self) -> bool:
        return False

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            content=self._response_text,
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=10, output_tokens=20),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        yield CompletionChunk(delta=self._response_text, done=False)
        yield CompletionChunk(delta="", done=True)
```

Create `examples/minimal_agent.py`:

```python
"""examples/minimal_agent.py — Tier 1: the smallest possible OOAgent.

No tools, no custom domain context, no telemetry — just a query and a
validated Artifact back. ContextRegistry falls back to NullContext
automatically when nothing is registered (CLAUDE.md §9).

Run: uv run python -m examples.minimal_agent

To use a real LLM backend instead of DemoLLMClient, replace the
llm_client below with, e.g.:

    import os
    from ooagent.adapters.llm.anthropic import AnthropicConfig, AnthropicLLMClient
    llm_client = AnthropicLLMClient(
        AnthropicConfig(api_key=os.environ["ANTHROPIC_API_KEY"], model="claude-opus-4-6"),
    )

Nothing else in this file changes.
"""

from __future__ import annotations

import asyncio

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import AgentConfig, Query

from ._common import DemoLLMClient


async def main() -> None:
    agent = OOAgent(llm_client=DemoLLMClient("Hello! I'm a validated OOAgent response."))

    await agent.initialize(AgentConfig())
    artifact = await agent.respond(Query(text="Hello, agent."))
    await agent.dispose()

    print(f"format:  {artifact.format}")
    print(f"content: {artifact.content}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/examples/test_examples.py -v`
Expected: PASS

- [ ] **Step 5: Run it directly, exactly as a user would**

Run: `uv run python -m examples.minimal_agent`
Expected:
```
format:  text
content: Hello! I'm a validated OOAgent response.
```

- [ ] **Step 6: Lint and commit**

Run: `uv run ruff check && uv run ruff format --check`
Expected: both report no findings

```bash
git add examples/__init__.py examples/_common.py examples/minimal_agent.py tests/examples/__init__.py tests/examples/test_examples.py
git commit -m "feat(examples): add minimal_agent golden-path example (Tier 1)"
```

---

### Task 2: `tool_enabled_agent.py` (Tier 2)

**Files:**
- Create: `examples/tool_enabled_agent.py`
- Modify: `tests/examples/test_examples.py` (append one test)

**Interfaces:**
- Consumes: `DemoLLMClient` (Task 1); `OOAgent`, `AgentConfig`, `Query` (as Task 1); `ToolRegistry` (`ooagent.core.registry`); `CalculatorTool` (`ooagent.plugins.tool_kit.calculator_tool` — already ships in the framework, `name = "calculator"`).
- Produces: `main()` coroutine in `examples/tool_enabled_agent.py` — consumed only by this task's test.

- [ ] **Step 1: Write the failing test**

Append to `tests/examples/test_examples.py` (add `from examples.tool_enabled_agent import main as tool_main` to the imports, alphabetically after the `minimal_agent` import):

```python
async def test_tool_enabled_agent_registers_calculator(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await tool_main()
    captured = capsys.readouterr()
    assert "registered tools: ['calculator']" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src uv run pytest tests/examples/test_examples.py::test_tool_enabled_agent_registers_calculator -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'examples.tool_enabled_agent'`

- [ ] **Step 3: Write the implementation**

Create `examples/tool_enabled_agent.py`:

```python
"""examples/tool_enabled_agent.py — Tier 2: an OOAgent with a registered tool.

Adds a ToolRegistry containing the framework's built-in CalculatorTool
(plugins/tool_kit/calculator_tool.py) — no new tool code needed to see
tool registration and injection working end-to-end.

Run: uv run python -m examples.tool_enabled_agent
"""

from __future__ import annotations

import asyncio

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import AgentConfig, Query
from ooagent.core.registry import ToolRegistry
from ooagent.plugins.tool_kit.calculator_tool import CalculatorTool

from ._common import DemoLLMClient


async def main() -> None:
    tool_registry = ToolRegistry()
    tool_registry.register(CalculatorTool())

    agent = OOAgent(
        llm_client=DemoLLMClient("I have access to a calculator tool if you need arithmetic."),
        tool_registry=tool_registry,
    )

    await agent.initialize(AgentConfig())
    artifact = await agent.respond(Query(text="What tools do you have?"))
    await agent.dispose()

    print(f"registered tools: {[t.name for t in tool_registry.all()]}")
    print(f"format:  {artifact.format}")
    print(f"content: {artifact.content}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/examples/ -v`
Expected: PASS (both tests)

- [ ] **Step 5: Run it directly**

Run: `uv run python -m examples.tool_enabled_agent`
Expected:
```
registered tools: ['calculator']
format:  text
content: I have access to a calculator tool if you need arithmetic.
```

- [ ] **Step 6: Lint and commit**

Run: `uv run ruff check && uv run ruff format --check`
Expected: both report no findings

```bash
git add examples/tool_enabled_agent.py tests/examples/test_examples.py
git commit -m "feat(examples): add tool_enabled_agent golden-path example (Tier 2)"
```

---

### Task 3: `domain_context_agent.py` (Tier 3)

**Files:**
- Create: `examples/domain_context_agent.py`
- Modify: `tests/examples/test_examples.py` (append one test)

**Interfaces:**
- Consumes: `DemoLLMClient` (Task 1); `IDomainContext`, `AntiPattern`, `ArtifactPolicy`, `InputSpec`, `Invariant`, `ISolver`, `PipelineStep`, `ProblemClass`, `Term` (all from `ooagent.core.protocols`); `ContextRegistry` (`ooagent.core.registry`).
- Produces: `UnitConversionContext` class and `main()` coroutine in `examples/domain_context_agent.py` — consumed only by this task's test.

- [ ] **Step 1: Write the failing test**

Append to `tests/examples/test_examples.py` (add `from examples.domain_context_agent import main as domain_context_main` to the imports, alphabetically before `minimal_agent`):

```python
async def test_domain_context_agent_resolves_unit_conversion_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await domain_context_main()
    captured = capsys.readouterr()
    assert "resolved context: UnitConversion v1.0" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src uv run pytest tests/examples/test_examples.py::test_domain_context_agent_resolves_unit_conversion_context -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'examples.domain_context_agent'`

- [ ] **Step 3: Write the implementation**

Create `examples/domain_context_agent.py`:

```python
"""examples/domain_context_agent.py — Tier 3: a custom IDomainContext.

Defines UnitConversionContext, a small domain with real vocabulary
(units) and a system prompt extension. Demonstrates *context resolution
and injection* — ContextRegistry.resolve() scores a query against every
registered context's vocabulary, and a query mentioning "meters"/"feet"
resolves to UnitConversionContext instead of falling back to NullContext
(CLAUDE.md §9's resolution algorithm).

solvers() returns {} deliberately: this example is about context
resolution/injection, not solver dispatch, which is a separate, deeper
topic (see CLAUDE.md §4's Strategy pattern entry).

Run: uv run python -m examples.domain_context_agent
"""

from __future__ import annotations

import asyncio

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import (
    AgentConfig,
    AntiPattern,
    ArtifactPolicy,
    IDomainContext,
    InputSpec,
    Invariant,
    ISolver,
    PipelineStep,
    ProblemClass,
    Query,
    Term,
)
from ooagent.core.registry import ContextRegistry

from ._common import DemoLLMClient


class UnitConversionContext(IDomainContext):
    """A small domain: converting between measurement units."""

    @property
    def name(self) -> str:
        return "UnitConversion"

    @property
    def version(self) -> str:
        return "1.0"

    def vocabulary(self) -> set[Term]:
        return {
            Term(label="meters", definition="SI unit of length", canonical=True),
            Term(label="feet", definition="imperial unit of length", canonical=True),
            Term(label="kilograms", definition="SI unit of mass", canonical=True),
            Term(label="pounds", definition="imperial unit of mass", canonical=True),
        }

    def problem_classes(self) -> set[ProblemClass]:
        return {
            ProblemClass(
                name="UnitConversion",
                description="Convert a quantity from one unit to another",
                solver="unit_converter",
            )
        }

    def solvers(self) -> dict[str, ISolver]:
        return {}

    def invariants(self) -> list[Invariant]:
        return [
            Invariant(
                name="unit-tagged-result",
                condition="every converted quantity carries its target unit",
                severity="error",
                rationale="a bare number without a unit is not a valid conversion result",
            )
        ]

    def pipeline(self) -> list[PipelineStep]:
        return []

    def anti_patterns(self) -> list[AntiPattern]:
        return []

    def required_inputs(self, pc: ProblemClass) -> list[InputSpec]:
        return []

    def artifact_preferences(self) -> ArtifactPolicy:
        return ArtifactPolicy(
            preferred_formats=["text"],
            type_hints_required=False,
            comment_policy="none",
        )

    def system_prompt_extension(self) -> str:
        return (
            "UnitConversion v1.0 is active. Convert between the requested "
            "units and always state the target unit alongside the number."
        )

    def resolve_intent(self, query: Query) -> ProblemClass | None:
        return None


async def main() -> None:
    ctx_registry = ContextRegistry()
    ctx_registry.register(UnitConversionContext())

    query = Query(text="Convert 10 meters to feet.")
    resolved = ctx_registry.resolve(query)
    print(f"resolved context: {resolved.name} v{resolved.version}")

    agent = OOAgent(
        llm_client=DemoLLMClient("10 meters is approximately 32.8 feet."),
        ctx_registry=ctx_registry,
    )

    await agent.initialize(AgentConfig())
    artifact = await agent.respond(query)
    await agent.dispose()

    print(f"format:  {artifact.format}")
    print(f"content: {artifact.content}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/examples/ -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Run it directly**

Run: `uv run python -m examples.domain_context_agent`
Expected:
```
resolved context: UnitConversion v1.0
format:  text
content: 10 meters is approximately 32.8 feet.
```

- [ ] **Step 6: Lint and commit**

Run: `uv run ruff check && uv run ruff format --check`
Expected: both report no findings

```bash
git add examples/domain_context_agent.py tests/examples/test_examples.py
git commit -m "feat(examples): add domain_context_agent golden-path example (Tier 3)"
```

---

### Task 4: `telemetry_enabled_agent.py` (Tier 4)

**Files:**
- Create: `examples/telemetry_enabled_agent.py`
- Modify: `tests/examples/test_examples.py` (append one test)

**Interfaces:**
- Consumes: `DemoLLMClient` (Task 1); `OOAgent`, `AgentConfig`, `Query` (as Task 1); `ConsoleTelemetry` (`ooagent.telemetry.console`).
- Produces: `main()` coroutine in `examples/telemetry_enabled_agent.py` — consumed only by this task's test.

- [ ] **Step 1: Write the failing test**

Append to `tests/examples/test_examples.py` (add `from examples.telemetry_enabled_agent import main as telemetry_main` to the imports, alphabetically after `tool_enabled_agent`):

```python
async def test_telemetry_enabled_agent_emits_telemetry(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await telemetry_main()
    captured = capsys.readouterr()
    assert "[Telemetry]" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src uv run pytest tests/examples/test_examples.py::test_telemetry_enabled_agent_emits_telemetry -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'examples.telemetry_enabled_agent'`

- [ ] **Step 3: Write the implementation**

Create `examples/telemetry_enabled_agent.py`:

```python
"""examples/telemetry_enabled_agent.py — Tier 4: telemetry made visible.

Wires ConsoleTelemetry (telemetry/console.py) so running this prints
span/event lines alongside the artifact — the observability story you
can see, not just read about.

Run: uv run python -m examples.telemetry_enabled_agent
"""

from __future__ import annotations

import asyncio

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import AgentConfig, Query
from ooagent.telemetry.console import ConsoleTelemetry

from ._common import DemoLLMClient


async def main() -> None:
    agent = OOAgent(
        llm_client=DemoLLMClient("Here's your response, with telemetry visible above."),
        telemetry=ConsoleTelemetry(),
    )

    await agent.initialize(AgentConfig())
    artifact = await agent.respond(Query(text="Hello, agent."))
    await agent.dispose()

    print(f"format:  {artifact.format}")
    print(f"content: {artifact.content}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src uv run pytest tests/examples/ -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Run it directly**

Run: `uv run python -m examples.telemetry_enabled_agent`
Expected (exact timing numbers will vary):
```
[Telemetry] span "agent.turn" completed in 0ms
[Telemetry] event "turn.complete" {'context': 'NullContext', 'format': 'text', 'turn': 1}
format:  text
content: Here's your response, with telemetry visible above.
```

- [ ] **Step 6: Lint, full-suite check, and commit**

Run: `uv run ruff check && uv run ruff format --check`
Expected: both report no findings

Run: `PYTHONPATH=src uv run pytest tests/ -q`
Expected: all tests pass (old + new), no regressions

```bash
git add examples/telemetry_enabled_agent.py tests/examples/test_examples.py
git commit -m "feat(examples): add telemetry_enabled_agent golden-path example (Tier 4)"
```

---

### Task 5: `docs/ARCHITECTURE.md` — move deep architecture content out of README

**Files:**
- Create: `docs/ARCHITECTURE.md`

**Interfaces:**
- Consumes: nothing (documentation only, moved from the current `README.md`).
- Produces: nothing consumed by later tasks in this plan — Task 6's README rewrite links to this file.

- [ ] **Step 1: Create `docs/ARCHITECTURE.md`**

Create `docs/ARCHITECTURE.md`:

```markdown
# OOAgent — Architecture

> The deep-dive companion to [README.md](../README.md)'s golden path.
> Read this once you've run the examples and want to understand *why*
> the framework is built this way. For the authoritative, exhaustive
> contract (invariants, FSM, failure modes, extension protocol), see
> [CLAUDE.md](../CLAUDE.md).

---

## Architecture at a Glance

```
IAgent[TQuery, TResponse]
└── AbstractAgent
    └── LLMAgent
        └── OOAgent  ← composition root
            ├── ILLMClient          (Anthropic / OpenAI / Gemini / Ollama)
            ├── ContextRegistry     (active IDomainContext)
            ├── ToolRegistry        (registered ITools)
            ├── PluginRegistry      (IPlugin extensions)
            ├── SessionState        (turn-level FSM + Memento)
            ├── LifecycleManager    (init / dispose / circuit-breaker)
            ├── ResponsePipeline    (Chain of Responsibility validation)
            ├── SolverDispatcher    (Strategy selector per ProblemClass)
            ├── ArtifactFactory     (Factory Method per output format)
            ├── ConstraintEngine    (invariant enforcement)
            ├── ProvenanceTracker   (source / citation discipline)
            ├── TelemetryProvider   (observability hook)
            └── ResponseDecorator   (final enrichment pass)
```

**Design philosophy:** composition over inheritance. `OOAgent` is a composition root, not a monolith. Each collaborator owns exactly one concern.

---

## Project Structure

```
src/ooagent/
├── core/
│   ├── protocols.py      # All interfaces & types (zero runtime dependencies)
│   ├── agent.py          # AbstractAgent, LLMAgent, OOAgent — Template Method implementation
│   ├── state.py          # SessionState, FSM, Memento, Command log
│   ├── pipeline.py       # ResponsePipeline (CoR), ConstraintEngine
│   ├── artifacts.py      # ArtifactFactory, ProvenanceTracker, ResponseDecorator
│   ├── registry.py       # ContextRegistry (Singleton), ToolRegistry, PluginRegistry
│   ├── lifecycle.py      # LifecycleManager, HealthStatus, CircuitBreaker
│   └── orchestrator.py   # MultiAgentOrchestrator, SignalBus
│
├── adapters/
│   ├── llm/
│   │   ├── anthropic.py  # ILLMClient → Anthropic Messages API
│   │   ├── openai.py     # ILLMClient → OpenAI Chat API
│   │   ├── gemini.py     # ILLMClient → Gemini API
│   │   ├── ollama.py     # ILLMClient → Ollama (local)
│   │   └── caching_proxy.py  # CachingLLMProxy, ThrottlingLLMProxy (Proxy pattern)
│   ├── tools/
│   │   ├── base.py       # BaseTool abstract class
│   │   └── adapter.py    # ToolAdapter (Adapter pattern)
│   └── data/             # IDataStore protocol + in-memory implementation
│
├── contexts/
│   └── null_context.py   # NullContext (Null Object — safe default)
│
├── plugins/
│   ├── base_plugin.py    # AbstractPlugin — reduces IPlugin boilerplate
│   └── logging/ audit/ cache/ rate_limit/ scope_guard/ security/ opentelemetry/ tool_kit/
│
└── telemetry/
    ├── null_telemetry.py # NullTelemetry (no-op — default)
    ├── otel.py           # OpenTelemetryProvider
    └── console.py        # ConsoleTelemetry (development)

tests/
├── core/ adapters/ plugins/  # Unit tests mirroring src/ooagent/
├── conformance/              # IAgent / IDomainContext / ITool / ILLMClient conformance suites
├── stub_llm_client.py        # Deterministic ILLMClient for unit tests
├── null_context.py           # Re-exports NullContext
└── fixtures.py                # Common test doubles
```

---

## Agent FSM

```
IDLE → GATHERING → MODELING → SOLVING → VALIDATING → DELIVERING → IDLE
                                  └──(any failure)──► FAILURE → DELIVERING → IDLE
```

Illegal FSM transitions raise `FSMViolation`. The FSM is owned by `SessionState`; no external object may mutate it directly.

---

## Design Patterns Applied

| Category | Patterns |
|----------|----------|
| **Behavioral** | Strategy, Chain of Responsibility, Observer, Template Method, Command, State, Visitor, Iterator, Mediator |
| **Creational** | Factory Method, Abstract Factory, Prototype, Singleton |
| **Structural** | Adapter, Decorator, Composite, Proxy, Bridge, Flyweight, Null Object |

See [CLAUDE.md](../CLAUDE.md) §4 for the full pattern-to-implementation mapping.

---

## SOLID Compliance

| Principle | How OOAgent honors it |
|---|---|
| **SRP** | Each collaborator owns exactly one concern. Multi-concern requests are decomposed by `RequestController`. |
| **OCP** | Open to new backends, domains, tools, solvers, formats, and plugins via registered abstractions. Closed to modification. |
| **LSP** | Every `OOAgent` subtype satisfies `IAgent.respond()` with identical pre/postconditions. |
| **ISP** | Fine-grained interfaces: `IToolUser`, `IContextHost`, `IArtifactFactory` are independent. |
| **DIP** | Depends exclusively on abstractions (`ILLMClient`, `IDomainContext`, `ISolver`, `ITool`). No vendor SDK leaks into core. |

---

## Extending OOAgent

### Add a domain context

1. Implement `IDomainContext` (10 methods).
2. Write `CONTEXT.md` per the spec in [CLAUDE.md §14](../CLAUDE.md).
3. Write conformance tests (see [CLAUDE.md §17](../CLAUDE.md)).
4. Register: `context_registry.register(MyContext())`.
5. No edits to `core/` — OCP enforced.

### Add a tool

1. Extend `BaseTool` or implement `ITool`.
2. Register: `tool_registry.register(MyTool())`.

### Add a new LLM backend

1. Implement `ILLMClient`.
2. Inject at construction: `OOAgent(llm_client=MyClient())`.

### Add a plugin

```python
class MyPlugin(AbstractPlugin):
    plugin_id = "my-plugin"
    version = "1.0.0"

    def on_register(self, agent):
        ...  # register tools / contexts

    def on_dispose(self):
        ...  # release resources

    def contributes(self) -> PluginContributions:
        return PluginContributions(tools=[MyTool()])


plugin_registry.register(MyPlugin())
```

---

## Output Discipline

Every response is validated before emission:

- **Code** — complete, typed, runnable. No fill-in stubs. Explicit error paths.
- **Numbers** — every numeric claim carries `value + unit + SourceTag` (`measured | assumed | cited | derived`).
- **Recommendations** — falsifiable or measurable. No speculation.
- **Artifacts** — built exclusively via `ArtifactFactory`. Never free-form emission.
- **Invariants** — `ConstraintEngine.assert_all()` must pass before any artifact is emitted.
```

- [ ] **Step 2: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add ARCHITECTURE.md — deep-dive content moved out of README"
```

---

### Task 6: `README.md` rewrite — positioning-first, golden-path-led

**Files:**
- Modify: `README.md` (full rewrite)

**Interfaces:**
- Consumes: `docs/ARCHITECTURE.md` (Task 5, linked from the new README).
- Produces: nothing consumed by other tasks — final task.

- [ ] **Step 1: Replace the entire contents of `README.md`**

Replace `README.md` with:

```markdown
# OOAgent — Object-Oriented AI Agent Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](https://www.python.org/)

> A composition framework for building type-safe, provider-portable AI agents — validation, testability, and observability enforced by construction, not layered on after.

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

That's a complete turn through OOAgent's FSM (`IDLE → GATHERING → MODELING → SOLVING → VALIDATING → DELIVERING → IDLE`) — a query in, a constraint-validated `Artifact` out. No API key needed: this example uses a deterministic stand-in client so you can see it work before wiring a real backend.

Four tiered examples, each a complete runnable file:

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
```

- [ ] **Step 2: Confirm the golden path in the README actually works as written**

Run: `uv sync --extra dev --extra otel && uv run python -m examples.minimal_agent`
Expected: output matches exactly what's shown in the README's Golden Path section

- [ ] **Step 3: Run the full verification suite**

Run: `uv run mypy --strict && uv run ruff check && uv run ruff format --check && PYTHONPATH=src uv run pytest tests/ -q`
Expected: all pass — 0 mypy errors (unaffected by this plan), 0 ruff findings, full test suite green (old + 4 new example tests)

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README — positioning-first, golden-path-led"
```

---

## Final Verification (before finishing-a-development-branch)

After Task 6, confirm the whole branch is coherent:

```bash
uv run mypy --strict
uv run ruff check
uv run ruff format --check
PYTHONPATH=src uv run pytest tests/ -q
uv run python -m examples.minimal_agent
uv run python -m examples.tool_enabled_agent
uv run python -m examples.domain_context_agent
uv run python -m examples.telemetry_enabled_agent
```

All must exit 0 / print the expected output. `git diff --stat` against the branch's base should show only: `examples/` (5 new files), `tests/examples/` (2 new files), `docs/ARCHITECTURE.md` (new), `README.md` (rewritten). No file under `src/ooagent/core/`, `adapters/`, `contexts/`, `plugins/`, or `telemetry/` should appear.
