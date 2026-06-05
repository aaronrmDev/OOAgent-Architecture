// adapters/tools/adapter.ts — ToolAdapter (Adapter pattern)
import { ITool, LLMVendor, VendorToolSpec } from '../../core/protocols.js'

// Mediates between tool invocations and vendor-specific tool-call schemas — §3 GRASP
export class ToolAdapter {
  toVendorSpecs(tools: ITool[], vendor: LLMVendor): VendorToolSpec[] {
    return tools.map(t => t.toVendorSpec(vendor))
  }
}
