// adapters/llm/openai.ts — ILLMClient → OpenAI Chat Completions API
import {
  CompletionChunk,
  CompletionRequest,
  CompletionResponse,
  ILLMClient,
  LLMVendor,
  TokenLimitError,
} from '../../core/protocols.js'

export interface OpenAIConfig {
  apiKey: string
  model?: string
  maxTokens?: number
  baseUrl?: string
}

interface OpenAIChoice {
  message: {
    role: string
    content: string | null
    tool_calls?: Array<{
      id: string
      type: string
      function: { name: string; arguments: string }
    }>
  }
  finish_reason: string
}

interface OpenAIChatResponse {
  id: string
  choices: OpenAIChoice[]
  usage: { prompt_tokens: number; completion_tokens: number }
}

export class OpenAILLMClient implements ILLMClient {
  readonly vendor: LLMVendor = 'openai'
  readonly modelId: string
  readonly maxTokens: number
  readonly supportsTools = true

  private readonly _apiKey: string
  private readonly _baseUrl: string

  constructor(config: OpenAIConfig) {
    this._apiKey = config.apiKey
    this.modelId = config.model ?? 'gpt-4o'
    this.maxTokens = config.maxTokens ?? 4096
    this._baseUrl = config.baseUrl ?? 'https://api.openai.com'
  }

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    if (this._estimateTokens(request) > this.maxTokens) {
      throw new TokenLimitError(this._estimateTokens(request), this.maxTokens)
    }

    const response = await fetch(`${this._baseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this._apiKey}`,
      },
      body: JSON.stringify(this._buildBody(request)),
    })

    if (!response.ok) {
      throw new Error(`OpenAI API error: ${response.status} ${response.statusText}`)
    }

    return this._parse(await response.json() as OpenAIChatResponse)
  }

  async *stream(request: CompletionRequest): AsyncIterableIterator<CompletionChunk> {
    const response = await fetch(`${this._baseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this._apiKey}`,
      },
      body: JSON.stringify({ ...this._buildBody(request), stream: true }),
    })

    if (!response.ok || !response.body) {
      throw new Error(`OpenAI stream error: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value)
      for (const line of text.split('\n').filter(l => l.startsWith('data: '))) {
        const json = line.slice(6).trim()
        if (json === '[DONE]') { yield { delta: '', done: true }; return }
        try {
          const event = JSON.parse(json) as {
            choices?: Array<{ delta?: { content?: string } }>
          }
          const delta = event.choices?.[0]?.delta?.content
          if (delta) yield { delta, done: false }
        } catch { /* skip malformed events */ }
      }
    }
    yield { delta: '', done: true }
  }

  private _buildBody(request: CompletionRequest): Record<string, unknown> {
    const body: Record<string, unknown> = {
      model: this.modelId,
      max_tokens: request.maxTokens ?? this.maxTokens,
      messages: request.messages.map(m => ({ role: m.role, content: m.content })),
    }
    if (request.tools?.length) {
      body['tools'] = request.tools
      body['tool_choice'] = 'auto'
    }
    if (request.temperature !== undefined) body['temperature'] = request.temperature
    if (request.stopSequences?.length) body['stop'] = request.stopSequences
    return body
  }

  private _parse(data: OpenAIChatResponse): CompletionResponse {
    const choice = data.choices[0]
    if (!choice) throw new Error('OpenAI returned no choices')

    const toolCalls = choice.message.tool_calls?.map(tc => ({
      id: tc.id,
      name: tc.function.name,
      args: JSON.parse(tc.function.arguments) as Record<string, unknown>,
    }))

    return {
      content: choice.message.content ?? '',
      stopReason: choice.finish_reason === 'tool_calls' ? 'tool_use'
        : choice.finish_reason === 'length' ? 'max_tokens'
        : 'end_turn',
      usage: {
        inputTokens: data.usage.prompt_tokens,
        outputTokens: data.usage.completion_tokens,
      },
      toolCalls,
    }
  }

  private _estimateTokens(request: CompletionRequest): number {
    return Math.ceil(request.messages.reduce((s, m) => s + m.content.length, 0) / 4)
  }
}
