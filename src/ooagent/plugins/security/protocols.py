"""plugins/security/protocols.py — Security contracts for OOAgent plugins.

Maps to: OWASP LLM Top 10 (2025), NIST AI RMF, ISO 27001/27002,
         GDPR Art.25, SOC 2 Type II, NIST SP 800-207 Zero Trust,
         SLSA L3, OWASP ASVS, PCI DSS 4.0, HIPAA.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

# ── OWASP LLM Top 10 risk identifiers ────────────────────────────────────────

OWASPLLMRisk = Literal[
    "LLM01_PROMPT_INJECTION",  # input overrides system instructions
    "LLM02_INSECURE_OUTPUT",  # unvalidated output executed as code
    "LLM03_TRAINING_DATA_POISONING",  # compromised training data
    "LLM04_MODEL_DOS",  # resource exhaustion via long inputs
    "LLM05_SUPPLY_CHAIN",  # compromised dependencies/plugins
    "LLM06_SENSITIVE_DISCLOSURE",  # model leaks PII from context
    "LLM07_INSECURE_PLUGIN",  # plugin executes without auth/validation
    "LLM08_EXCESSIVE_AGENCY",  # agent takes unintended high-impact actions
    "LLM09_OVERRELIANCE",  # system over-trusts model output without validation
    "LLM10_MODEL_THEFT",  # extraction via adversarial prompting
]

# ── Compliance frameworks ─────────────────────────────────────────────────────

ComplianceFramework = Literal[
    "OWASP_LLM_TOP10",
    "OWASP_API_TOP10",
    "NIST_AI_RMF",
    "ISO_27001",
    "GDPR_ART25",
    "SOC2_TYPE2",
    "NIST_SP800_207",  # Zero Trust
    "SLSA_L3",
    "OWASP_ASVS",
    "PCI_DSS_4",
    "HIPAA",
]

# ── Security events ───────────────────────────────────────────────────────────

SecurityEventSeverity = Literal["info", "low", "medium", "high", "critical"]


@dataclass(frozen=True)
class SecurityEvent:
    id: str
    timestamp: str  # ISO 8601 UTC
    severity: SecurityEventSeverity
    risk: OWASPLLMRisk | str
    framework: ComplianceFramework
    message: str
    agent_id: str
    remediation: str
    tool_name: str | None = None
    input: str | None = None  # sanitized — no raw PII


# ── Policy types ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RateLimitPolicy:
    max_calls_per_minute: int
    max_calls_per_hour: int
    max_input_tokens: int  # LLM04: Model DoS prevention


@dataclass(frozen=True)
class InputValidationPolicy:
    max_input_length: int  # LLM04: DoS prevention
    blocked_patterns: list[str]  # LLM01: Prompt injection patterns
    allowed_hosts: list[str]  # SSRF prevention (OWASP API7)
    pii_masking_enabled: bool  # GDPR Art.25 / LLM06


@dataclass(frozen=True)
class OutputValidationPolicy:
    max_output_length: int  # LLM02: Insecure output
    html_escape_enabled: bool  # OWASP ASVS V5.3
    json_parse_strict: bool  # LLM02: type enforcement


@dataclass(frozen=True)
class AccessControlPolicy:
    rbac_enabled: bool  # OWASP API1/2, SOC2 CC6.1
    allowed_agent_ids: list[str]  # Zero Trust: never trust, always verify
    allowed_tools: list[str]  # Least privilege (NIST SP 800-207)
    require_mfa: bool  # SOC2 CC6.1


@dataclass(frozen=True)
class AuditPolicy:
    enabled: bool  # SOC2 CC6.2, HIPAA 164.312(b)
    include_input: bool  # note: PII must be masked first
    include_output: bool
    retention_days: int  # GDPR / PCI DSS compliance
    sink: Callable[[SecurityEvent], Any] | None = None


@dataclass(frozen=True)
class BudgetPolicy:
    max_cost_usd_per_hour: float  # OWASP LLM09: unbounded consumption
    max_tool_calls_per_turn: int  # LLM08: Excessive agency
    alert_threshold_pct: float  # alert at X% of budget


@dataclass(frozen=True)
class SecurityPolicy:
    policy_id: str
    version: str
    frameworks: list[ComplianceFramework]
    rate_limit: RateLimitPolicy
    input: InputValidationPolicy
    output: OutputValidationPolicy
    access: AccessControlPolicy
    audit: AuditPolicy
    budget: BudgetPolicy


# ── Interfaces ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SecurityValidationResult:
    allowed: bool
    reason: str | None = None
    risk: OWASPLLMRisk | str | None = None


class ISecurityPolicy(ABC):
    """Enforces compliance controls on every plugin tool call.
    A single shared instance per agent (Singleton pattern, SOC2 CC9.1).
    """

    @property
    @abstractmethod
    def policy(self) -> SecurityPolicy: ...

    @abstractmethod
    def validate_input(self, input: dict[str, Any], tool_name: str) -> SecurityValidationResult:
        """Validates input before tool execution (LLM01, LLM04, GDPR Art.25)."""

    @abstractmethod
    def validate_output(self, output: Any, tool_name: str) -> SecurityValidationResult:
        """Validates output before returning to agent (LLM02, OWASP ASVS V5.3)."""

    @abstractmethod
    def check_access(self, agent_id: str, tool_name: str) -> SecurityValidationResult:
        """Checks access rights (OWASP API1/2, Zero Trust, SOC2 CC6.1)."""

    @abstractmethod
    def record(
        self,
        *,
        severity: SecurityEventSeverity,
        risk: OWASPLLMRisk | str,
        framework: ComplianceFramework,
        message: str,
        agent_id: str,
        remediation: str,
        tool_name: str | None = None,
        input: str | None = None,
    ) -> None:
        """Records a security event (SOC2 CC6.2, HIPAA 164.312(b), PCI DSS 10.2)."""
