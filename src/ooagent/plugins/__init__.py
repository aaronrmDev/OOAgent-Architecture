"""ooagent/plugins/__init__.py — barrel export for all plugin capabilities.

Note on `plugins/registry.ts`: in the TS source this file is a pure
re-export of `core/registry.ts`'s `PluginRegistry` (`export {
PluginRegistry } from '../core/registry.js'`). No separate
`ooagent/plugins/registry.py` module is created for the same reason —
`PluginRegistry` is re-exported directly from `ooagent.core.registry`
below, avoiding a duplicate definition.

The `tool-kit` and `security` plugin groups (`ToolKitPlugin`,
`DateTimeTool`, `CalculatorTool`, `HttpFetchTool`, `SecurityPlugin`,
`DefaultSecurityPolicy`, `DEFAULT_SECURITY_POLICY`, `SecureToolWrapper`,
and their associated option/policy types) are added to this barrel in
Task 16 — intentionally NOT imported here yet, to avoid a hard dependency
on modules this task does not own.
"""

from __future__ import annotations

from ooagent.core.registry import PluginRegistry

from ooagent.plugins.audit import AuditEntry, AuditPlugin, AuditPluginOptions
from ooagent.plugins.base_plugin import AbstractPlugin
from ooagent.plugins.cache import CachePlugin, CachePluginOptions
from ooagent.plugins.logging import LoggingPlugin, LoggingPluginOptions
from ooagent.plugins.opentelemetry import OpenTelemetryPlugin, OtelPluginOptions
from ooagent.plugins.rate_limit import RateLimitOptions, RateLimitPlugin
from ooagent.plugins.scope_guard import ScopeGuardOptions, ScopeGuardPlugin

__all__ = [
    "AbstractPlugin",
    "PluginRegistry",
    "LoggingPlugin",
    "LoggingPluginOptions",
    "RateLimitPlugin",
    "RateLimitOptions",
    "CachePlugin",
    "CachePluginOptions",
    "OpenTelemetryPlugin",
    "OtelPluginOptions",
    "AuditPlugin",
    "AuditPluginOptions",
    "AuditEntry",
    "ScopeGuardPlugin",
    "ScopeGuardOptions",
]
