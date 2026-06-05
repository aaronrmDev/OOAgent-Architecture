// plugins/tool-kit/datetime-tool.ts — DateTimeTool
import { BaseTool } from '../../adapters/tools/base.js'
import { JSONSchema } from '../../core/protocols.js'

export class DateTimeTool extends BaseTool {
  readonly name        = 'datetime'
  readonly description = 'Returns the current UTC date and time in ISO 8601 format.'

  inputSchema(): JSONSchema {
    return {
      type: 'object',
      properties: {
        timezone: {
          type: 'string',
          description: 'IANA timezone string (e.g. "America/New_York"). Defaults to UTC.',
        },
      },
      required: [],
    }
  }

  async execute(args: Record<string, unknown>): Promise<unknown> {
    const tz = (args.timezone as string | undefined) ?? 'UTC'
    try {
      return {
        iso: new Date().toLocaleString('sv-SE', { timeZone: tz }).replace(' ', 'T') + 'Z',
        timezone: tz,
      }
    } catch {
      return { iso: new Date().toISOString(), timezone: 'UTC' }
    }
  }
}
