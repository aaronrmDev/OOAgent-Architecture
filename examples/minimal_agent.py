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
