"""adapters/tools/base.py — BaseTool abstract class (Adapter pattern)."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from ooagent.core.protocols import (
    ITool,
    JSONSchema,
    LLMVendor,
    ToolExecutionError,
    VendorToolSpec,
)


class BaseTool(ITool):
    """Partial ITool implementation — concrete tools implement name, description,
    input_schema(), and execute(); to_vendor_spec() and _validate_args() are
    provided here."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def input_schema(self) -> JSONSchema: ...

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> Any: ...

    def to_vendor_spec(self, vendor: LLMVendor) -> VendorToolSpec:
        """Adapter — translates ITool to vendor-specific tool-call schema — §4 GoF."""
        schema = self.input_schema()
        if vendor == "anthropic":
            return {
                "name": self.name,
                "description": self.description,
                "input_schema": schema,
            }
        if vendor in ("openai", "ollama"):
            return {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": schema,
                },
            }
        if vendor == "gemini":
            return {
                "function_declarations": [
                    {
                        "name": self.name,
                        "description": self.description,
                        "parameters": schema,
                    }
                ]
            }
        # Exhaustive fallback — mirrors the TS `never`-typed exhaustiveness check.
        return {
            "name": self.name,
            "description": self.description,
            "schema": schema,
            "vendor": vendor,
        }

    def _validate_args(self, args: dict[str, Any]) -> None:
        """Validates required fields before execution — always call from execute()."""
        schema = self.input_schema()
        required = schema.get("required") or []
        for key in required:
            if key not in args or args[key] is None:
                raise ToolExecutionError(
                    self.name, args, ValueError(f"Missing required argument: {key}")
                )
