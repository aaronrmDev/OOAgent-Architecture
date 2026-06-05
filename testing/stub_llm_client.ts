// testing/stub_llm_client.ts — Deterministic ILLMClient for unit tests
import {
  CompletionChunk,
  CompletionRequest,
  CompletionResponse,
  ILLMClient,
  LLMVendor,
  TokenLimitError,
} from '../core/protocols.js'

interface ScriptEntry {
  pattern: RegExp | string
  response: Partial<CompletionResponse>
}

// Scripted responses keyed by message content pattern — §17 CLAUDE.md
export class StubLLMClient implements ILLMClient {
  readonly vendor: LLMVendor
  readonly modelId: string
  readonly maxTokens: number
  readonly supportsTools: boolean

  private readonly _scripts: ScriptEntry[] = []
  private _callCount = 0

  constructor(options: {
    vendor?: LLMVendor
    model?: string
    maxTokens?: number
    supportsTools?: boolean
  } = {}) {
    this.vendor = options.vendor ?? 'anthropic'
    this.modelId = options.model ?? 'stub-1.0'
    this.maxTokens = options.maxTokens ?? 4096
    this.supportsTools = options.supportsTools ?? false
  }

  // Fluent API for scripting responses
  addScript(pattern: RegExp | string, response: Partial<CompletionResponse>): this {
    this._scripts.push({ pattern, response })
    return this
  }

  get callCount(): number { return this._callCount }

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    this._callCount++
    const estimated = Math.ceil(
      request.messages.reduce((s, m) => s + m.content.length, 0) / 4,
    )
    if (estimated > this.maxTokens) {
      throw new TokenLimitError(estimated, this.maxTokens)
    }

    const lastUser = [...request.messages]
      .reverse()
      .find(m => m.role === 'user')?.content ?? ''

    for (const entry of this._scripts) {
      const matches =
        typeof entry.pattern === 'string'
          ? lastUser.includes(entry.pattern)
          : entry.pattern.test(lastUser)
      if (matches) {
        return {
          content: entry.response.content ?? 'Stub response.',
          stopReason: entry.response.stopReason ?? 'end_turn',
          usage: entry.response.usage ?? { inputTokens: 10, outputTokens: 20 },
          toolCalls: entry.response.toolCalls,
        }
      }
    }

    return {
      content: 'Default stub response.',
      stopReason: 'end_turn',
      usage: { inputTokens: 10, outputTokens: 20 },
    }
  }

  async *stream(request: CompletionRequest): AsyncIterableIterator<CompletionChunk> {
    const response = await this.complete(request)
    yield { delta: response.content, done: false }
    yield { delta: '', done: true }
  }
}
