// adapters/llm/anthropic.ts — ILLMClient → Anthropic Messages API
import {
  CompletionChunk,
  CompletionRequest,
  CompletionResponse,
  ILLMClient,
  LLMVendor,
  TokenLimitError,
} from '../../core/protocols.js'

export interface AnthropicConfig {
  apiKey: string
  model?: string
  maxTokens?: number
  baseUrl?: string
}

interface AnthropicContentBlock {
  type: string
  text?: string
  id?: string
  name?: string
  input?: Record<string, unknown>
}

interface AnthropicMessageResponse {
  id: string
  type: string
  role: string
  content: AnthropicContentBlock[]
  model: string
  stop_reason: string
  usage: { input_tokens: number; output_tokens: number }
}

export class AnthropicLLMClient implements ILLMClient {
  readonly vendor: LLMVendor = 'anthropic'
  readonly modelId: string
  readonly maxTokens: number
  readonly supportsTools = true

  private readonly _apiKey: string
  private readonly _baseUrl: string

  constructor(config: AnthropicConfig) {
    this._apiKey = config.apiKey
    this.modelId = config.model ?? 'claude-opus-4-6'
    this.maxTokens = config.maxTokens ?? 8192
    this._baseUrl = config.baseUrl ?? 'https://api.anthropic.com'
  }

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    if (this._estimateTokens(request) > this.maxTokens) {
      throw new TokenLimitError(this._estimateTokens(request), this.maxTokens)
    }

    const response = await fetch(`${this._baseUrl}/v1/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': this._apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify(this._buildBody(request)),
    })

    if (!response.ok) {
      throw new Error(`Anthropic API error: ${response.status} ${response.statusText}`)
    }

    return this._parse(await response.json() as AnthropicMessageResponse)
  }

  async *stream(request: CompletionRequest): AsyncIterableIterator<CompletionChunk> {
    const response = await fetch(`${this._baseUrl}/v1/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': this._apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({ ...this._buildBody(request), stream: true }),
    })

    if (!response.ok || !response.body) {
      throw new Error(`Anthropic stream error: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value)
      for (const line of text.split('\n').filter(l => l.startsWith('data: '))) {
        const json = line.slice(6)
        if (json.trim() === '[DONE]') { yield { delta: '', done: true }; return }
        try {
          const event = JSON.parse(json) as {
            type: string
            delta?: { type: string; text?: string }
          }
          if (event.type === 'content_block_delta' && event.delta?.text) {
            yield { delta: event.delta.text, done: false }
          }
        } catch { /* skip malformed events */ }
      }
    }
    yield { delta: '', done: true }
  }

  private _buildBody(request: CompletionRequest): Record<string, unknown> {
    const system = request.messages.find(m => m.role === 'system')?.content
    const messages = request.messages
      .filter(m => m.role !== 'system')
      .map(m => ({ role: m.role, content: m.content }))

    const body: Record<string, unknown> = {
      model: this.modelId,
      max_tokens: request.maxTokens ?? this.maxTokens,
      messages,
    }
    if (system) body['system'] = system
    if (request.tools?.length) body['tools'] = request.tools
    if (request.temperature !== undefined) body['temperature'] = request.temperature
    if (request.stopSequences?.length) body['stop_sequences'] = request.stopSequences
    return body
  }

  private _parse(data: AnthropicMessageResponse): CompletionResponse {
    const textBlock = data.content.find(b => b.type === 'text')
    const toolBlocks = data.content.filter(b => b.type === 'tool_use')
    return {
      content: textBlock?.text ?? '',
      stopReason: data.stop_reason === 'tool_use' ? 'tool_use'
        : data.stop_reason === 'max_tokens' ? 'max_tokens'
        : 'end_turn',
      usage: {
        inputTokens: data.usage.input_tokens,
        outputTokens: data.usage.output_tokens,
      },
      toolCalls: toolBlocks.map(b => ({
        id: b.id ?? '',
        name: b.name ?? '',
        args: b.input ?? {},
      })),
    }
  }

  private _estimateTokens(request: CompletionRequest): number {
    const chars = request.messages.reduce((s, m) => s + m.content.length, 0)
    return Math.ceil(chars / 4)
  }
}
