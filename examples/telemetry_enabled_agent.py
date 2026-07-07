"""examples/telemetry_enabled_agent.py — Tier 4: telemetry made visible.

Wires ConsoleTelemetry (telemetry/console.py) so running this prints
span/event lines alongside the artifact — the observability story you
can see, not just read about.

Run: uv run python -m examples.telemetry_enabled_agent

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
