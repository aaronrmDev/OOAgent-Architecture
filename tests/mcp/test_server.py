"""tests/mcp/test_server.py — MCP server integration tests (in-process client)."""

from __future__ import annotations

from mcp.shared.memory import create_connected_server_and_client_session

from ooagent.contexts.null_context import NullContext
from ooagent.core.agent import OOAgent
from ooagent.core.protocols import AgentConfig
from ooagent.core.registry import ContextRegistry
from ooagent.mcp.server import build_server
from tests.stub_llm_client import StubLLMClient


async def _build_test_agent() -> tuple[OOAgent, list]:
    ctx_registry = ContextRegistry()
    null_context = NullContext()
    ctx_registry.register(null_context)
    agent = OOAgent(llm_client=StubLLMClient(), ctx_registry=ctx_registry)
    await agent.initialize(AgentConfig())
    return agent, [null_context]


async def test_respond_tool_returns_agent_response() -> None:
    agent, contexts = await _build_test_agent()
    server = build_server(agent, contexts)

    async with create_connected_server_and_client_session(server) as client:
        await client.initialize()
        result = await client.call_tool("respond", {"query": "hello agent"})

        assert result.isError is False
        assert result.content[0].text == "Default stub response."

    await agent.dispose()


async def test_respond_tool_is_listed() -> None:
    agent, contexts = await _build_test_agent()
    server = build_server(agent, contexts)

    async with create_connected_server_and_client_session(server) as client:
        await client.initialize()
        tools = await client.list_tools()
        assert "respond" in [t.name for t in tools.tools]

    await agent.dispose()


async def test_contexts_resource_lists_null_context() -> None:
    agent, contexts = await _build_test_agent()
    server = build_server(agent, contexts)

    async with create_connected_server_and_client_session(server) as client:
        await client.initialize()
        resources = await client.list_resources()
        assert "contexts://list" in [str(r.uri) for r in resources.resources]

        result = await client.read_resource("contexts://list")
        assert "NullContext" in result.contents[0].text

    await agent.dispose()
