"""tests/plugins/test_plugins_part1.py — audit, cache, logging, rate_limit, scope_guard plugins."""

from __future__ import annotations

import pytest

from ooagent.core.protocols import Artifact, Query, ScopeExitError
from ooagent.plugins.audit import AuditPlugin
from ooagent.plugins.cache import CachePlugin
from ooagent.plugins.logging import LoggingPlugin, LoggingPluginOptions
from ooagent.plugins.rate_limit import RateLimitOptions, RateLimitPlugin
from ooagent.plugins.scope_guard import ScopeGuardOptions, ScopeGuardPlugin


class _EchoTool:
    name = "echo"
    description = "echoes"

    def input_schema(self):
        return {}

    async def execute(self, args):
        return args

    def to_vendor_spec(self, vendor):
        return {}


class _FakeAgent:
    agent_id = "agent-1"


def test_audit_plugin_records_decorator_invocation_in_ring_buffer() -> None:
    plugin = AuditPlugin()
    plugin.on_register(_FakeAgent())
    contributions = plugin.contributes()
    decorator = contributions.decorators[0]
    artifact = Artifact(content="hi", format="text", provenance=[], metadata={"contextName": "Engineering"})
    decorator(artifact, [])
    assert len(plugin.entries) == 1
    assert plugin.entries[0].context_name == "Engineering"


async def test_cache_plugin_caches_tool_result_on_second_call() -> None:
    calls = {"n": 0}

    class _CountingTool(_EchoTool):
        async def execute(self, args):
            calls["n"] += 1
            return {"result": args}

    plugin = CachePlugin()
    plugin.cache_tools(_CountingTool())
    contributions = plugin.contributes()
    cached_tool = contributions.tools[0]
    await cached_tool.execute({"x": 1})
    await cached_tool.execute({"x": 1})
    assert calls["n"] == 1


def test_logging_plugin_writes_through_custom_sink() -> None:
    lines = []
    plugin = LoggingPlugin(LoggingPluginOptions(sink=lines.append))
    plugin.on_register(_FakeAgent())
    assert any("registered" in line for line in lines)


async def test_rate_limited_tool_blocks_after_max_calls() -> None:
    plugin = RateLimitPlugin(RateLimitOptions(max_calls=1, window_ms=60_000))
    plugin.wrap_tools(_EchoTool())
    contributions = plugin.contributes()
    wrapped = contributions.tools[0]
    await wrapped.execute({"a": 1})
    with pytest.raises(Exception):
        await wrapped.execute({"a": 2})


async def test_scope_guard_blocks_query_matching_pattern() -> None:
    plugin = ScopeGuardPlugin(ScopeGuardOptions(blocked_patterns=["forbidden"]))
    contributions = plugin.contributes()
    context = contributions.contexts[0]
    step = context.pipeline()[0]
    with pytest.raises(ScopeExitError):
        await step.run(Query(text="this is a forbidden topic"), context)
