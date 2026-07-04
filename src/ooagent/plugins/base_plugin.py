"""plugins/base_plugin.py — AbstractPlugin: reduces boilerplate for IPlugin implementors."""

from __future__ import annotations

from typing import Any

from ooagent.core.protocols import IAgent, IPlugin, PluginContributions


class AbstractPlugin(IPlugin):
    """Abstract base for IPlugin implementors.

    Subclasses must still declare `plugin_id` and `version` (left abstract
    here, mirroring the TS `abstract readonly pluginId: string`).
    """

    def on_register(self, agent: IAgent[Any, Any]) -> None:
        """Called once by PluginRegistry.register() → OOAgent.initialize().
        Override to perform setup (register event listeners, open connections, etc.)."""
        return None

    def on_dispose(self) -> None:
        """Override to release resources allocated in on_register.
        Must be idempotent — may be called more than once."""
        return None

    def contributes(self) -> PluginContributions:
        """Override to declare what this plugin contributes to the agent."""
        return PluginContributions()
