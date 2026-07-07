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
