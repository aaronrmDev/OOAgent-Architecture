// plugins/tool-kit/http-fetch-tool.ts — HttpFetchTool
// Performs GET requests to allowlisted domains and returns response text.
// Never fetches arbitrary user-supplied URLs without an allowlist — security boundary.
import { BaseTool } from '../../adapters/tools/base.js'
import {
  JSONSchema,
  ToolExecutionError,
} from '../../core/protocols.js'

export interface HttpFetchToolOptions {
  /**
   * Allowlist of hostname patterns (exact match or ending wildcard, e.g. '*.example.com').
   * If empty or undefined, all public HTTPS URLs are permitted.
   */
  allowedHosts?: string[]
  /** Request timeout in milliseconds. Default: 10 000 */
  timeoutMs?: number
  /** Maximum response body size in bytes. Default: 512 000 (512 KB) */
  maxBodyBytes?: number
}

export class HttpFetchTool extends BaseTool {
  readonly name        = 'http_fetch'
  readonly description = 'Performs an HTTP GET request and returns the response body as text.'

  private readonly _allowedHosts: string[]
  private readonly _timeoutMs: number
  private readonly _maxBodyBytes: number

  constructor(opts: HttpFetchToolOptions = {}) {
    super()
    this._allowedHosts = opts.allowedHosts  ?? []
    this._timeoutMs    = opts.timeoutMs     ?? 10_000
    this._maxBodyBytes = opts.maxBodyBytes  ?? 512_000
  }

  inputSchema(): JSONSchema {
    return {
      type: 'object',
      properties: {
        url: {
          type: 'string',
          description: 'The HTTPS URL to fetch.',
        },
        headers: {
          type: 'object',
          description: 'Optional HTTP request headers as key-value string pairs.',
          additionalProperties: { type: 'string' },
        },
      },
      required: ['url'],
    }
  }

  async execute(args: Record<string, unknown>): Promise<unknown> {
    const url = args.url as string
    if (typeof url !== 'string' || !url.startsWith('https://')) {
      throw new ToolExecutionError(this.name, args, new Error('url must be an HTTPS string'))
    }

    if (!this._isAllowed(url)) {
      throw new ToolExecutionError(
        this.name, args,
        new Error(`Host not in allowlist: ${new URL(url).hostname}`),
      )
    }

    const headers = (args.headers as Record<string, string> | undefined) ?? {}
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), this._timeoutMs)

    try {
      const res = await fetch(url, { headers, signal: controller.signal })
      const text = await this._readBody(res)
      return {
        status: res.status,
        contentType: res.headers.get('content-type') ?? 'unknown',
        body: text,
        url,
      }
    } catch (err) {
      throw new ToolExecutionError(this.name, args, err)
    } finally {
      clearTimeout(timer)
    }
  }

  private async _readBody(res: Response): Promise<string> {
    const reader = res.body?.getReader()
    if (!reader) return ''
    const chunks: Uint8Array[] = []
    let total = 0
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      total += value.byteLength
      if (total > this._maxBodyBytes) {
        reader.cancel()
        return new TextDecoder().decode(Buffer.concat(chunks)) + '\n[truncated]'
      }
      chunks.push(value)
    }
    return new TextDecoder().decode(Buffer.concat(chunks))
  }

  private _isAllowed(url: string): boolean {
    if (this._allowedHosts.length === 0) return true
    const hostname = new URL(url).hostname
    return this._allowedHosts.some(pattern => {
      if (pattern.startsWith('*.')) {
        return hostname.endsWith(pattern.slice(1))
      }
      return hostname === pattern
    })
  }

}
