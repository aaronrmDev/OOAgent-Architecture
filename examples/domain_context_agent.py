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

See CONTEXT_EXAMPLE.md alongside this file for a worked example of the
CLAUDE.md §14 CONTEXT.md format, filled out for UnitConversionContext.

Run: uv run python -m examples.domain_context_agent

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
    print(f"system prompt extension: {resolved.system_prompt_extension()}")

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
