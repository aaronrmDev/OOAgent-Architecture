"""ooagent/plugins/__init__.py — barrel export for all plugin capabilities."""

from __future__ import annotations

from ooagent.core.registry import PluginRegistry
from ooagent.plugins.audit import AuditEntry, AuditPlugin, AuditPluginOptions
from ooagent.plugins.base_plugin import AbstractPlugin
from ooagent.plugins.cache import CachePlugin, CachePluginOptions
from ooagent.plugins.logging import LoggingPlugin, LoggingPluginOptions
from ooagent.plugins.opentelemetry import OpenTelemetryPlugin, OtelPluginOptions
from ooagent.plugins.rate_limit import RateLimitOptions, RateLimitPlugin
from ooagent.plugins.scope_guard import ScopeGuardOptions, ScopeGuardPlugin
from ooagent.plugins.security import (
    DEFAULT_SECURITY_POLICY,
    DefaultSecurityPolicy,
    SecureToolWrapper,
    SecurityPlugin,
    SecurityPluginOptions,
)
from ooagent.plugins.tool_kit import (
    CalculatorTool,
    DateTimeTool,
    HttpFetchTool,
    HttpFetchToolOptions,
    ToolKitPlugin,
    ToolKitPluginOptions,
)

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
    "DefaultSecurityPolicy",
    "DEFAULT_SECURITY_POLICY",
    "SecureToolWrapper",
    "SecurityPlugin",
    "SecurityPluginOptions",
    "CalculatorTool",
    "DateTimeTool",
    "HttpFetchTool",
    "HttpFetchToolOptions",
    "ToolKitPlugin",
    "ToolKitPluginOptions",
]
