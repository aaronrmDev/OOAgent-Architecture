// plugins/tool-kit/index.ts — ToolKitPlugin
// Bundles DateTimeTool, CalculatorTool, and HttpFetchTool into a single plugin.
import { PluginContributions } from '../../core/protocols.js'
import { AbstractPlugin } from '../base-plugin.js'
import { CalculatorTool } from './calculator-tool.js'
import { DateTimeTool } from './datetime-tool.js'
import { HttpFetchTool, HttpFetchToolOptions } from './http-fetch-tool.js'

export { CalculatorTool }                        from './calculator-tool.js'
export { DateTimeTool }                          from './datetime-tool.js'
export { HttpFetchTool }                         from './http-fetch-tool.js'
export type { HttpFetchToolOptions }             from './http-fetch-tool.js'

export interface ToolKitPluginOptions {
  httpFetch?: HttpFetchToolOptions | false
  datetime?:  boolean
  calculator?: boolean
}

export class ToolKitPlugin extends AbstractPlugin {
  readonly pluginId = 'ooagent.tool-kit'
  readonly version  = '1.0.0'

  private readonly _opts: ToolKitPluginOptions

  constructor(opts: ToolKitPluginOptions = {}) {
    super()
    this._opts = { datetime: true, calculator: true, httpFetch: {}, ...opts }
  }

  override contributes(): PluginContributions {
    const tools = []
    if (this._opts.datetime    !== false) tools.push(new DateTimeTool())
    if (this._opts.calculator  !== false) tools.push(new CalculatorTool())
    if (this._opts.httpFetch   !== false) {
      tools.push(new HttpFetchTool(
        typeof this._opts.httpFetch === 'object' ? this._opts.httpFetch : {},
      ))
    }
    return { tools }
  }
}
