"""ooagent/mcp/server.py — OOAgent MCP server (FastMCP, stdio transport).

Owns MCP-protocol concerns only (tool/resource registration, the entry
point). Agent construction is config.py's job (Information Expert).
"""

from __future__ import annotations

import sys

import anyio
from mcp.server.fastmcp import FastMCP

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import AgentConfig, IDomainContext, Query

from .config import ConfigError, build_agent


def build_server(agent: OOAgent, contexts: list[IDomainContext]) -> FastMCP:
    mcp_server = FastMCP("ooagent")

    @mcp_server.tool()
    async def respond(query: str) -> str:
        """Send a query to the OOAgent instance and return its response."""
        artifact = await agent.respond(Query(text=query))
        return artifact.content

    @mcp_server.resource("contexts://list")
    def list_contexts() -> str:
        """List the domain contexts currently registered with this OOAgent instance."""
        lines = [f"{ctx.name} v{ctx.version}" for ctx in contexts]
        return "\n".join(lines) if lines else "(no domain contexts registered)"

    return mcp_server


async def _serve() -> None:
    try:
        agent, contexts = build_agent()
    except ConfigError as err:
        print(f"ooagent-mcp: {err}", file=sys.stderr)
        raise SystemExit(1) from err

    await agent.initialize(AgentConfig())
    mcp_server = build_server(agent, contexts)
    try:
        await mcp_server.run_stdio_async()
    finally:
        await agent.dispose()


def main() -> None:
    anyio.run(_serve)


if __name__ == "__main__":
    main()
