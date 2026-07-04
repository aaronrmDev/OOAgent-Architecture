"""plugins/security/secure_tool_wrapper.py — SecureToolWrapper.

Wraps any ITool with the full security policy gate.

Every call to execute() is intercepted:
  1. Access control check  (Zero Trust, RBAC, SOC2)
  2. Input validation      (LLM01, LLM04, LLM06, GDPR)
  3. Delegated execution   (original tool)
  4. Output validation     (LLM02, ASVS V5.3)
  5. Audit record          (SOC2, HIPAA, PCI DSS)
"""

from __future__ import annotations

import time
from typing import Any

from ooagent.core.protocols import ITool, JSONSchema, LLMVendor, VendorToolSpec
from ooagent.plugins.security.protocols import ISecurityPolicy


class SecureToolWrapper(ITool):
    def __init__(
        self, inner: ITool, policy: ISecurityPolicy, agent_id: str = "unknown"
    ) -> None:
        self._inner = inner
        self._policy = policy
        self._agent_id = agent_id

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def description(self) -> str:
        return self._inner.description

    def input_schema(self) -> JSONSchema:
        return self._inner.input_schema()

    def to_vendor_spec(self, vendor: LLMVendor) -> VendorToolSpec:
        return self._inner.to_vendor_spec(vendor)

    def set_agent_id(self, id: str) -> None:
        self._agent_id = id

    async def execute(self, args: dict[str, Any]) -> Any:
        tool = self.name
        agent = self._agent_id

        # ① Zero Trust access check (NIST SP 800-207, OWASP API1/2, SOC2 CC6.1)
        access = self._policy.check_access(agent, tool)
        if not access.allowed:
            return self._denied("Access denied", access.reason or "Policy violation", tool)

        # ② Input validation (LLM01, LLM04, LLM06, GDPR Art.25)
        input_check = self._policy.validate_input(args, tool)
        if not input_check.allowed:
            return self._denied(
                "Input validation failed", input_check.reason or "Policy violation", tool
            )

        # ③ Execute original tool
        start = time.time()
        try:
            result = await self._inner.execute(args)
        except Exception as err:
            self._policy.record(
                severity="medium",
                risk="LLM07_INSECURE_PLUGIN",
                framework="ISO_27001",
                message=f"Tool '{tool}' threw: {err}",
                agent_id=agent,
                tool_name=tool,
                remediation=(
                    "Ensure tool.execute() throws ToolExecutionError with descriptive message"
                ),
            )
            raise

        # ④ Output validation (LLM02, OWASP ASVS V5.3)
        output_check = self._policy.validate_output(result, tool)
        if not output_check.allowed:
            return self._denied(
                "Output validation failed", output_check.reason or "Policy violation", tool
            )

        # ⑤ Audit record (SOC2 CC6.2, HIPAA 164.312(b), PCI DSS 10.2)
        elapsed_ms = round((time.time() - start) * 1000)
        self._policy.record(
            severity="info",
            risk="N/A",
            framework="SOC2_TYPE2",
            message=f"Tool '{tool}' executed successfully in {elapsed_ms}ms",
            agent_id=agent,
            tool_name=tool,
            remediation="No action required",
        )

        return result

    @staticmethod
    def _denied(type_: str, reason: str, tool_name: str) -> dict[str, str]:
        return {
            "error": type_,
            "reason": reason,
            "tool": tool_name,
            "status": "blocked_by_security_policy",
        }
