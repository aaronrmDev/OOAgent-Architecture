"""tests/conformance/test_plugin.py — IPlugin conformance suite (§17 CLAUDE.md)."""

from __future__ import annotations

import pytest

from ooagent.core.agent import NULL_TELEMETRY
from ooagent.core.protocols import (
    Artifact,
    IAgent,
    IPlugin,
    ISessionState,
    PluginContributions,
    Query,
)
from ooagent.plugins.audit import AuditPlugin
from ooagent.plugins.cache import CachePlugin
from ooagent.plugins.logging import LoggingPlugin
from ooagent.plugins.opentelemetry import OpenTelemetryPlugin, OtelPluginOptions
from ooagent.plugins.rate_limit import RateLimitPlugin
from ooagent.plugins.scope_guard import ScopeGuardPlugin
from ooagent.plugins.security import SecurityPlugin
from ooagent.plugins.tool_kit import ToolKitPlugin


class _StubAgent(IAgent[Query, Artifact]):
    @property
    def agent_id(self) -> str:
        return "stub-agent"

    @property
    def state(self) -> ISessionState:
        raise NotImplementedError

    async def respond(self, query: Query) -> Artifact:
        raise NotImplementedError


def _all_plugins() -> list[object]:
    # Constructed fresh per call (not a module-level constant) so each test
    # gets its own plugin instances — on_dispose in one test must not affect
    # on_register in another.
    return [
        AuditPlugin(),
        CachePlugin(),
        LoggingPlugin(),
        OpenTelemetryPlugin(OtelPluginOptions(provider=NULL_TELEMETRY)),
        RateLimitPlugin(),
        ScopeGuardPlugin(),
        SecurityPlugin(),
        ToolKitPlugin(),
    ]


@pytest.mark.parametrize("plugin", _all_plugins(), ids=lambda p: p.plugin_id)
def test_plugin_id_and_version_are_non_empty_strings(plugin: IPlugin) -> None:
    assert isinstance(plugin.plugin_id, str) and plugin.plugin_id
    assert isinstance(plugin.version, str) and plugin.version


@pytest.mark.parametrize("plugin", _all_plugins(), ids=lambda p: p.plugin_id)
def test_plugin_contributes_returns_plugin_contributions(plugin: IPlugin) -> None:
    assert isinstance(plugin.contributes(), PluginContributions)


@pytest.mark.parametrize("plugin", _all_plugins(), ids=lambda p: p.plugin_id)
def test_plugin_on_register_does_not_raise(plugin: IPlugin) -> None:
    plugin.on_register(_StubAgent())


@pytest.mark.parametrize("plugin", _all_plugins(), ids=lambda p: p.plugin_id)
def test_plugin_on_dispose_is_idempotent(plugin: IPlugin) -> None:
    plugin.on_dispose()
    plugin.on_dispose()  # must not raise
