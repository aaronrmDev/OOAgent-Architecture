"""ooagent.mcp — MCP (Model Context Protocol) server: OOAgent as a host-agnostic plugin."""

from ooagent.mcp.config import ConfigError, build_agent, build_llm_client
from ooagent.mcp.server import build_server, main

__all__ = [
    "ConfigError",
    "build_agent",
    "build_llm_client",
    "build_server",
    "main",
]
