"""plugins/security/__init__.py — SecurityPlugin.

Wraps ITool instances with the full security gate. There are two supported
recipes for this — both require explicit consumer action, since
`OOAgent.initialize()` registers each plugin's `contributes()` tools directly
into its own `ToolRegistry` as it iterates plugins; there is no hook where
`SecurityPlugin` automatically sees tools contributed by *other* plugins:

  1. Construction-time wrapping — pass the tool instances you already hold
     as `SecurityPluginOptions.tools_to_wrap`; `contributes()` returns them
     pre-wrapped in `SecureToolWrapper`.

  2. Post-initialize registry wrapping — construct your own `ToolRegistry`
     instance and pass it to `OOAgent(tool_registry=...)`. Because the agent
     stores that same instance, you hold a live reference to it. After
     `await agent.initialize(config)` has populated it with every plugin's
     contributed tools, call `security_plugin.wrap_registry(that_registry)`
     to wrap all of them in place. See `wrap_registry()` below.

Compliance coverage:
  OWASP LLM Top 10 (2025) — all 10 risks addressed
  OWASP API Top 10        — API1 (broken object auth), API2 (auth), API4 (rate limit),
                            API6 (business flow), API7 (SSRF)
  NIST AI RMF             — Map, Measure, Manage phases
  ISO 27001/27002         — A.6.2, A.8.1, A.12, A.13, A.14, A.18.1
  GDPR Article 25         — data minimization, PII masking, audit trails
  SOC 2 Type II           — CC6.1, CC6.2, CC7.2, CC9.1, CC9.2
  NIST SP 800-207         — Zero Trust: never trust, always verify
  SLSA L3                 — signed plugin provenance (audit log as attestation)
  OWASP ASVS              — V4.1, V5.3, V11.1
  PCI DSS 4.0             — Req 2.1, 6.3, 10.2
  HIPAA                   — 164.308(a)(3)(ii)(B), 164.312(a)(2)(i), 164.312(b)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ooagent.core.protocols import IAgent, IPlugin, ITool, PluginContributions
from ooagent.plugins.security.policy_engine import (
    DEFAULT_SECURITY_POLICY,
    DefaultSecurityPolicy,
)
from ooagent.plugins.security.protocols import (
    AccessControlPolicy,
    AuditPolicy,
    BudgetPolicy,
    ComplianceFramework,
    InputValidationPolicy,
    ISecurityPolicy,
    OutputValidationPolicy,
    OWASPLLMRisk,
    RateLimitPolicy,
    SecurityEvent,
    SecurityEventSeverity,
    SecurityPolicy,
    SecurityValidationResult,
)
from ooagent.plugins.security.secure_tool_wrapper import SecureToolWrapper

__all__ = [
    "DefaultSecurityPolicy",
    "DEFAULT_SECURITY_POLICY",
    "SecureToolWrapper",
    "ISecurityPolicy",
    "SecurityPolicy",
    "SecurityEvent",
    "SecurityEventSeverity",
    "OWASPLLMRisk",
    "ComplianceFramework",
    "RateLimitPolicy",
    "InputValidationPolicy",
    "OutputValidationPolicy",
    "AccessControlPolicy",
    "AuditPolicy",
    "BudgetPolicy",
    "SecurityValidationResult",
    "SecurityPluginOptions",
    "SecurityPlugin",
]


class IToolRegistryRuntime(Protocol):
    def all(self) -> list[ITool]: ...
    def register(self, tool: ITool) -> None: ...


@dataclass
class SecurityPluginOptions:
    """Options accepted by :class:`SecurityPlugin`."""

    policy: dict[str, Any] | None = None
    # Reserved for a caller-held ToolRegistry reference; SecurityPlugin does
    # not read this field itself. To wrap an externally-held registry, call
    # `SecurityPlugin.wrap_registry(that_registry)` directly after
    # `agent.initialize()` completes (see `wrap_registry()` below) — passing
    # the registry here has no effect.
    tool_registry: IToolRegistryRuntime | None = None
    # Tool instances to wrap via contributes(). Populate at construction
    # time, before registering this plugin with the agent's PluginRegistry —
    # contributes() (invoked during agent.initialize()) returns each of
    # these pre-wrapped in a SecureToolWrapper.
    tools_to_wrap: list[ITool] = field(default_factory=list)


class SecurityPlugin(IPlugin):
    plugin_id = "ooagent.security"
    version = "2026.06.01"

    def __init__(self, opts: SecurityPluginOptions | None = None) -> None:
        opts = opts or SecurityPluginOptions()
        self._security_policy = DefaultSecurityPolicy(opts.policy)
        self._agent_id = "<unregistered>"
        self._tools_to_wrap: list[ITool] = list(opts.tools_to_wrap)

    @property
    def security_policy(self) -> DefaultSecurityPolicy:
        return self._security_policy

    def on_register(self, agent: IAgent[Any, Any]) -> None:
        self._agent_id = agent.agent_id

    def on_dispose(self) -> None:
        return None

    def contributes(self) -> PluginContributions:
        wrapped: list[ITool] = [
            SecureToolWrapper(t, self._security_policy, self._agent_id) for t in self._tools_to_wrap
        ]
        return PluginContributions(tools=wrapped)

    def wrap_registry(self, registry: IToolRegistryRuntime) -> None:
        """Wraps every tool currently in a ToolRegistry.

        Call AFTER `agent.initialize(config)` has completed — that is what
        populates the registry with every other plugin's contributed tools
        (see `OOAgent.initialize()` in core/agent.py). `registry` must be the
        same `ToolRegistry` instance passed to `OOAgent(tool_registry=...)`,
        so the wrapped tools this method registers are visible to the agent.
        """
        tools = registry.all()
        for tool in tools:
            wrapped = SecureToolWrapper(tool, self._security_policy, self._agent_id)
            registry.register(wrapped)

    @property
    def audit_log(self) -> tuple[SecurityEvent, ...]:
        """Returns the audit log of all security events."""
        return self._security_policy.audit_log

    @staticmethod
    def mask_pii(text: str) -> str:
        """Mask PII in any string (GDPR Art.25)."""
        return DefaultSecurityPolicy.mask_pii(text)
