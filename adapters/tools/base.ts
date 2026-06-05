// adapters/tools/base.ts — BaseTool abstract class (Adapter pattern)
import {
  ITool,
  JSONSchema,
  LLMVendor,
  ToolExecutionError,
  VendorToolSpec,
} from '../../core/protocols.js'

export abstract class BaseTool implements ITool {
  abstract readonly name: string
  abstract readonly description: string

  abstract inputSchema(): JSONSchema
  abstract execute(args: Record<string, unknown>): Promise<unknown>

  // Adapter — translates ITool to vendor-specific tool-call schema — §4 GoF
  toVendorSpec(vendor: LLMVendor): VendorToolSpec {
    const schema = this.inputSchema()
    switch (vendor) {
      case 'anthropic':
        return {
          name: this.name,
          description: this.description,
          input_schema: schema,
        }
      case 'openai':
      case 'ollama':
        return {
          type: 'function',
          function: {
            name: this.name,
            description: this.description,
            parameters: schema,
          },
        }
      case 'gemini':
        return {
          function_declarations: [
            {
              name: this.name,
              description: this.description,
              parameters: schema,
            },
          ],
        }
      default: {
        const exhaustive: never = vendor
        return {
          name: this.name,
          description: this.description,
          schema,
          vendor: exhaustive,
        }
      }
    }
  }

  // Validates required fields before execution — always call in execute()
  protected validateArgs(args: Record<string, unknown>): void {
    const schema = this.inputSchema() as {
      required?: string[]
      properties?: Record<string, unknown>
    }
    for (const key of schema.required ?? []) {
      if (!(key in args) || args[key] === undefined || args[key] === null) {
        throw new ToolExecutionError(
          this.name,
          args,
          new Error(`Missing required argument: ${key}`),
        )
      }
    }
  }
}
