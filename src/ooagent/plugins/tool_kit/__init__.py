"""plugins/tool_kit/__init__.py — ToolKitPlugin.

Bundles DateTimeTool, CalculatorTool, and HttpFetchTool into a single plugin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ooagent.core.protocols import ITool, PluginContributions
from ooagent.plugins.base_plugin import AbstractPlugin
from ooagent.plugins.tool_kit.calculator_tool import CalculatorTool
from ooagent.plugins.tool_kit.datetime_tool import DateTimeTool
from ooagent.plugins.tool_kit.http_fetch_tool import HttpFetchTool, HttpFetchToolOptions

__all__ = [
    "CalculatorTool",
    "DateTimeTool",
    "HttpFetchTool",
    "HttpFetchToolOptions",
    "ToolKitPluginOptions",
    "ToolKitPlugin",
]


@dataclass
class ToolKitPluginOptions:
    http_fetch: HttpFetchToolOptions | Literal[False] = field(default_factory=HttpFetchToolOptions)
    datetime: bool = True
    calculator: bool = True


class ToolKitPlugin(AbstractPlugin):
    plugin_id = "ooagent.tool-kit"
    version = "1.0.0"

    def __init__(self, opts: ToolKitPluginOptions | None = None) -> None:
        self._opts = opts or ToolKitPluginOptions()

    def on_dispose(self) -> None:
        return None

    def contributes(self) -> PluginContributions:
        tools: list[ITool] = []
        if self._opts.datetime is not False:
            tools.append(DateTimeTool())
        if self._opts.calculator is not False:
            tools.append(CalculatorTool())
        if self._opts.http_fetch is not False:
            http_opts = (
                self._opts.http_fetch
                if isinstance(self._opts.http_fetch, HttpFetchToolOptions)
                else HttpFetchToolOptions()
            )
            tools.append(HttpFetchTool(http_opts))
        return PluginContributions(tools=tools)
