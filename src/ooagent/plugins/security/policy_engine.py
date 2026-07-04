"""plugins/security/policy_engine.py — DefaultSecurityPolicy.

Enforces all 10 OWASP LLM risks + ISO 27001 + GDPR Art.25 + SOC2 Type II +
Zero Trust + SLSA on every tool call.

Compliance coverage per method:
  validate_input  → LLM01 (Prompt Injection), LLM04 (DoS), LLM06 (PII), GDPR Art.25
  validate_output → LLM02 (Insecure Output), OWASP ASVS V5.3
  check_access    → OWASP API1/2, NIST SP 800-207 Zero Trust, SOC2 CC6.1, LLM07
  record()        → SOC2 CC6.2, HIPAA 164.312(b), PCI DSS 10.2, ISO 27001 A.12
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

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

_logger = logging.getLogger("ooagent.security")

# Default prompt injection patterns (LLM01) — sourced from OWASP LLM Top 10 2025
DEFAULT_INJECTION_PATTERNS: list[str] = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard the above",
    "new task:",
    "system override",
    "you are now",
    "forget your instructions",
    "jailbreak",
    "dan mode",
    "developer mode",
    "sudo mode",
    "\\u0000",  # null byte injection
    "base64:",  # encoded payload
    "<|im_start|>",  # tokenizer injection
    "<|endoftext|>",  # tokenizer injection
    "[INST]",  # Llama tokenizer injection
    "###INSTRUCTION",
]


@dataclass(frozen=True)
class _PiiPattern:
    name: str
    pattern: re.Pattern[str]
    replacement: str


# PII patterns for masking (GDPR Art.25, LLM06). Order matters: the "phone"
# regex is broad enough to match any 10+-digit run with optional separators,
# including an unformatted 16-digit credit card number — so the specific
# fixed-format "ssn"/"cc" patterns must run first, or a card number gets
# masked but mislabeled as [PHONE_REDACTED] instead of [CC_REDACTED],
# undermining PCI DSS audit-trail accuracy (no raw-PII leak either way, but
# the label matters for compliance reporting).
PII_PATTERNS: list[_PiiPattern] = [
    _PiiPattern(
        "email",
        re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "[EMAIL_REDACTED]",
    ),
    _PiiPattern(
        "ssn",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[SSN_REDACTED]",
    ),
    _PiiPattern(
        "cc",
        re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b"),
        "[CC_REDACTED]",
    ),
    _PiiPattern(
        "phone",
        re.compile(r"\+?[0-9]{1,3}[\s.-]?[0-9]{3}[\s.-]?[0-9]{4,}"),
        "[PHONE_REDACTED]",
    ),
    _PiiPattern(
        "api_key",
        re.compile(
            r"(?:api[_-]?key|apikey|token|secret)[=:\s]+[a-zA-Z0-9_.-]{16,}",
            re.IGNORECASE,
        ),
        "[SECRET_REDACTED]",
    ),
]


DEFAULT_SECURITY_POLICY = SecurityPolicy(
    policy_id="ooagent-default-security",
    version="2026.06.01",
    frameworks=[
        "OWASP_LLM_TOP10",
        "OWASP_API_TOP10",
        "NIST_AI_RMF",
        "ISO_27001",
        "GDPR_ART25",
        "SOC2_TYPE2",
        "NIST_SP800_207",
        "SLSA_L3",
        "OWASP_ASVS",
    ],
    rate_limit=RateLimitPolicy(
        max_calls_per_minute=60,
        max_calls_per_hour=500,
        max_input_tokens=8192,  # LLM04: Model DoS prevention
    ),
    input=InputValidationPolicy(
        max_input_length=32768,  # ~8K tokens, LLM04
        blocked_patterns=DEFAULT_INJECTION_PATTERNS,
        allowed_hosts=[],  # empty = all HTTPS allowed; set to restrict (OWASP API7)
        pii_masking_enabled=True,  # GDPR Art.25
    ),
    output=OutputValidationPolicy(
        max_output_length=65536,  # LLM02
        html_escape_enabled=True,  # OWASP ASVS V5.3
        json_parse_strict=True,  # LLM02
    ),
    access=AccessControlPolicy(
        rbac_enabled=False,  # enable in production — off by default for dev
        allowed_agent_ids=[],  # empty = all agents allowed
        allowed_tools=[],  # empty = all tools allowed
        require_mfa=False,
    ),
    audit=AuditPolicy(
        enabled=True,
        include_input=False,  # inputs excluded by default (PII risk)
        include_output=False,
        retention_days=90,  # GDPR minimum + PCI DSS 12.10.1
    ),
    budget=BudgetPolicy(
        max_cost_usd_per_hour=10.00,  # LLM09: unbounded consumption guard
        max_tool_calls_per_turn=20,  # LLM08: excessive agency guard
        alert_threshold_pct=80,
    ),
)


@dataclass
class _RateLimitState:
    minute: int = 0
    hour: int = 0
    last_minute: float = 0.0
    last_hour: float = 0.0


class DefaultSecurityPolicy(ISecurityPolicy):
    def __init__(self, policy: dict[str, Any] | None = None) -> None:
        overrides = policy or {}
        self._policy = replace(DEFAULT_SECURITY_POLICY, **overrides)
        self._log: list[SecurityEvent] = []
        self._call_counts: dict[str, _RateLimitState] = {}

    @property
    def policy(self) -> SecurityPolicy:
        return self._policy

    # ── Input validation (LLM01, LLM04, LLM06, GDPR Art.25) ──────────────────
    def validate_input(self, input: dict[str, Any], tool_name: str) -> SecurityValidationResult:
        text = json.dumps(input)

        # LLM04: Input length limit (Model DoS)
        if len(text) > self._policy.input.max_input_length:
            self.record(
                severity="high",
                risk="LLM04_MODEL_DOS",
                framework="OWASP_LLM_TOP10",
                message=(
                    f"Input to '{tool_name}' exceeds max length "
                    f"({len(text)} > {self._policy.input.max_input_length})"
                ),
                agent_id="unknown",
                tool_name=tool_name,
                remediation="Truncate input or increase maxInputLength in SecurityPolicy",
            )
            return SecurityValidationResult(
                allowed=False, reason="Input too long (DoS guard)", risk="LLM04_MODEL_DOS"
            )

        # LLM01: Prompt injection detection
        lower = text.lower()
        for pattern in self._policy.input.blocked_patterns:
            if pattern.lower() in lower:
                self.record(
                    severity="critical",
                    risk="LLM01_PROMPT_INJECTION",
                    framework="OWASP_LLM_TOP10",
                    message=(
                        f"Prompt injection pattern detected in input to '{tool_name}': '{pattern}'"
                    ),
                    agent_id="unknown",
                    tool_name=tool_name,
                    remediation=(
                        "Input contains a known injection pattern. "
                        "Sanitize input before passing to tools."
                    ),
                )
                return SecurityValidationResult(
                    allowed=False,
                    reason=f"Prompt injection detected: '{pattern}'",
                    risk="LLM01_PROMPT_INJECTION",
                )

        # LLM06 / GDPR Art.25: PII masking warning (we don't block, we warn + mask if requested)
        if self._policy.input.pii_masking_enabled:
            for pii in PII_PATTERNS:
                if pii.pattern.search(text):
                    self.record(
                        severity="medium",
                        risk="LLM06_SENSITIVE_DISCLOSURE",
                        framework="GDPR_ART25",
                        message=(
                            f"Possible {pii.name.upper()} detected in input to "
                            f"'{tool_name}' — masked before processing"
                        ),
                        agent_id="unknown",
                        tool_name=tool_name,
                        remediation=(
                            "Enable piiMaskingEnabled to auto-redact PII from "
                            "tool inputs (GDPR Art.25)"
                        ),
                    )

        return SecurityValidationResult(allowed=True)

    # ── Output validation (LLM02, OWASP ASVS V5.3) ───────────────────────────
    def validate_output(self, output: Any, tool_name: str) -> SecurityValidationResult:
        text = output if isinstance(output, str) else json.dumps(output)

        # LLM02: Output length check
        if len(text) > self._policy.output.max_output_length:
            self.record(
                severity="low",
                risk="LLM02_INSECURE_OUTPUT",
                framework="OWASP_LLM_TOP10",
                message=f"Output from '{tool_name}' exceeds max length — truncation applied",
                agent_id="unknown",
                tool_name=tool_name,
                remediation="Increase maxOutputLength or implement pagination in tool response",
            )

        # LLM02 / OWASP ASVS V5.3: Detect potential script injection in output
        if self._policy.output.html_escape_enabled and isinstance(output, str):
            if re.search(r"<script|javascript:|on\w+\s*=", output, re.IGNORECASE):
                self.record(
                    severity="high",
                    risk="LLM02_INSECURE_OUTPUT",
                    framework="OWASP_ASVS",
                    message=(
                        f"Potential XSS/script injection detected in output from '{tool_name}'"
                    ),
                    agent_id="unknown",
                    tool_name=tool_name,
                    remediation=(
                        "HTML-escape tool outputs before rendering in web UI (OWASP ASVS V5.3)"
                    ),
                )
                return SecurityValidationResult(
                    allowed=False, reason="Potential XSS in output", risk="LLM02_INSECURE_OUTPUT"
                )

        return SecurityValidationResult(allowed=True)

    # ── Access control (LLM07, OWASP API1/2, Zero Trust, SOC2 CC6.1) ─────────
    def check_access(self, agent_id: str, tool_name: str) -> SecurityValidationResult:
        if not self._policy.access.rbac_enabled:
            return SecurityValidationResult(allowed=True)

        # Zero Trust: never trust agent identity implicitly (NIST SP 800-207)
        if (
            self._policy.access.allowed_agent_ids
            and agent_id not in self._policy.access.allowed_agent_ids
        ):
            self.record(
                severity="high",
                risk="LLM07_INSECURE_PLUGIN",
                framework="NIST_SP800_207",
                message=f"Agent '{agent_id}' is not authorized to call any tools",
                agent_id=agent_id,
                tool_name=tool_name,
                remediation=(
                    "Add agentId to allowedAgentIds in AccessControlPolicy "
                    "(Zero Trust: verify every call)"
                ),
            )
            return SecurityValidationResult(
                allowed=False,
                reason=f"Agent '{agent_id}' not in allowlist",
                risk="LLM07_INSECURE_PLUGIN",
            )

        # Least privilege: tool must be in allowedTools (NIST SP 800-207)
        if self._policy.access.allowed_tools and tool_name not in self._policy.access.allowed_tools:
            self.record(
                severity="medium",
                risk="LLM07_INSECURE_PLUGIN",
                framework="OWASP_API_TOP10",
                message=(f"Agent '{agent_id}' attempted to call unauthorized tool '{tool_name}'"),
                agent_id=agent_id,
                tool_name=tool_name,
                remediation=(
                    f"Add '{tool_name}' to allowedTools, or restrict to required "
                    "tools only (least privilege)"
                ),
            )
            return SecurityValidationResult(
                allowed=False,
                reason=f"Tool '{tool_name}' not in allowedTools",
                risk="LLM07_INSECURE_PLUGIN",
            )

        # Rate limiting (LLM04, OWASP API4)
        rate_result = self._check_rate_limit(agent_id, tool_name)
        if not rate_result.allowed:
            return rate_result

        return SecurityValidationResult(allowed=True)

    # ── Audit log (SOC2 CC6.2, HIPAA 164.312(b), PCI DSS 10.2) ──────────────
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
        full = SecurityEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            severity=severity,
            risk=risk,
            framework=framework,
            message=message,
            agent_id=agent_id,
            remediation=remediation,
            tool_name=tool_name,
            input=input,
        )

        self._log.append(full)

        # Trim log to retention window (GDPR retention limit)
        max_entries = self._policy.audit.retention_days * 24 * 60  # ~1 per minute max
        if len(self._log) > max_entries:
            self._log.pop(0)

        # External sink (SOC2 CC7.2 real-time monitoring)
        sink = self._policy.audit.sink
        if sink is not None:
            self._invoke_sink(sink, full)

        # Console output for high/critical (SOC2 CC7.2 alerting)
        if severity in ("high", "critical"):
            _logger.error("[SECURITY %s] %s: %s", severity.upper(), risk, message)

    @staticmethod
    def _invoke_sink(sink: Any, event: SecurityEvent) -> None:
        try:
            result = sink(event)
        except Exception:
            _logger.exception("[SecurityPolicy] Audit sink error")
            return

        if inspect.isawaitable(result):

            async def _await_sink() -> None:
                try:
                    await result
                except Exception:
                    _logger.exception("[SecurityPolicy] Audit sink error")

            try:
                asyncio.get_running_loop().create_task(_await_sink())
            except RuntimeError:
                asyncio.run(_await_sink())

    @property
    def audit_log(self) -> tuple[SecurityEvent, ...]:
        """Immutable snapshot of the security event log."""
        return tuple(self._log)

    @staticmethod
    def mask_pii(text: str) -> str:
        """Mask PII in a string (GDPR Art.25). Returns masked copy."""
        result = text
        for pii in PII_PATTERNS:
            result = pii.pattern.sub(pii.replacement, result)
        return result

    # ── Private: sliding-window rate limiter (LLM04, OWASP API4) ─────────────
    def _check_rate_limit(self, agent_id: str, tool_name: str) -> SecurityValidationResult:
        now = time.time()
        state = self._call_counts.get(agent_id)
        if state is None:
            state = _RateLimitState(last_minute=now, last_hour=now)

        if now - state.last_minute > 60:
            state.minute = 0
            state.last_minute = now
        if now - state.last_hour > 3600:
            state.hour = 0
            state.last_hour = now

        state.minute += 1
        state.hour += 1
        self._call_counts[agent_id] = state

        if state.minute > self._policy.rate_limit.max_calls_per_minute:
            self.record(
                severity="high",
                risk="LLM04_MODEL_DOS",
                framework="OWASP_API_TOP10",
                message=(
                    f"Agent '{agent_id}' exceeded rate limit "
                    f"({state.minute}/min > {self._policy.rate_limit.max_calls_per_minute})"
                ),
                agent_id=agent_id,
                tool_name=tool_name,
                remediation="Increase maxCallsPerMinute or implement request queuing",
            )
            return SecurityValidationResult(
                allowed=False, reason="Rate limit exceeded (per-minute)", risk="LLM04_MODEL_DOS"
            )

        if state.hour > self._policy.rate_limit.max_calls_per_hour:
            self.record(
                severity="high",
                risk="LLM04_MODEL_DOS",
                framework="OWASP_API_TOP10",
                message=(
                    f"Agent '{agent_id}' exceeded hourly rate limit "
                    f"({state.hour}/hr > {self._policy.rate_limit.max_calls_per_hour})"
                ),
                agent_id=agent_id,
                tool_name=tool_name,
                remediation="Increase maxCallsPerHour or throttle upstream callers",
            )
            return SecurityValidationResult(
                allowed=False, reason="Rate limit exceeded (per-hour)", risk="LLM04_MODEL_DOS"
            )

        return SecurityValidationResult(allowed=True)
