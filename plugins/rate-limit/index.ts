// plugins/rate-limit/index.ts — RateLimitPlugin
// Wraps every registered ITool with a rate-limiting adapter that enforces
// a per-tool call budget (tokens per window).
import {
  IAgent,
  ITool,
  JSONSchema,
  LLMVendor,
  PluginContributions,
  ToolExecutionError,
  VendorToolSpec,
} from '../../core/protocols.js'
import { AbstractPlugin } from '../base-plugin.js'

export interface RateLimitOptions {
  /** Maximum calls allowed per window. Default: 60 */
  maxCalls?: number
  /** Window duration in milliseconds. Default: 60 000 (1 minute) */
  windowMs?: number
}

// Wraps an ITool and enforces a sliding-window call budget
class RateLimitedTool implements ITool {
  private _calls: number[] = []

  constructor(
    private readonly _inner: ITool,
    private readonly _maxCalls: number,
    private readonly _windowMs: number,
  ) {}

  get name():        string { return this._inner.name }
  get description(): string { return this._inner.description }
  inputSchema():     JSONSchema    { return this._inner.inputSchema() }
  toVendorSpec(v: LLMVendor): VendorToolSpec { return this._inner.toVendorSpec(v) }

  async execute(args: Record<string, unknown>): Promise<unknown> {
    const now = Date.now()
    this._calls = this._calls.filter(t => now - t < this._windowMs)

    if (this._calls.length >= this._maxCalls) {
      const oldestCall = this._calls[0]
      const retryAfterMs = this._windowMs - (now - oldestCall)
      throw new ToolExecutionError(
        this._inner.name,
        args,
        new Error(
          `Rate limit exceeded (${this._maxCalls} calls/${this._windowMs}ms). ` +
          `Retry after ${Math.ceil(retryAfterMs / 1000)}s.`,
        ),
      )
    }

    this._calls.push(now)
    return this._inner.execute(args)
  }
}

export class RateLimitPlugin extends AbstractPlugin {
  readonly pluginId = 'ooagent.rate-limit'
  readonly version  = '1.0.0'

  private readonly _maxCalls: number
  private readonly _windowMs: number
  private _toolsToWrap: ITool[] = []

  constructor(opts: RateLimitOptions = {}) {
    super()
    this._maxCalls = opts.maxCalls ?? 60
    this._windowMs = opts.windowMs ?? 60_000
  }

  // Call before initialize() to declare which tools to wrap.
  // If no tools are provided, no wrapping occurs at contribute() time.
  wrapTools(...tools: ITool[]): this {
    this._toolsToWrap = tools
    return this
  }

  override onRegister(_agent: IAgent<unknown, unknown>): void {}
  override onDispose(): void { this._toolsToWrap = [] }

  override contributes(): PluginContributions {
    const wrapped = this._toolsToWrap.map(
      t => new RateLimitedTool(t, this._maxCalls, this._windowMs),
    )
    return { tools: wrapped }
  }
}
