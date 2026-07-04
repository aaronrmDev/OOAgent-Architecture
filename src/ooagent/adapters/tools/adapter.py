"""adapters/tools/adapter.py — ToolAdapter (Adapter pattern)."""

from __future__ import annotations

from ooagent.core.protocols import ITool, LLMVendor, VendorToolSpec


class ToolAdapter:
    """Mediates between tool invocations and vendor-specific tool-call schemas — §3 GRASP."""

    def to_vendor_specs(self, tools: list[ITool], vendor: LLMVendor) -> list[VendorToolSpec]:
        return [t.to_vendor_spec(vendor) for t in tools]
