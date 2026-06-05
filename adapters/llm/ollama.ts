// adapters/llm/ollama.ts — ILLMClient → Ollama local API (OpenAI-compatible)
import {
  CompletionChunk,
  CompletionRequest,
  CompletionResponse,
  ILLMClient,
  LLMVendor,
} from '../../core/protocols.js'

export interface OllamaConfig {
  model?: string
  maxTokens?: number
  baseUrl?: string
}

interface OllamaChoice {
  message: { role: string; content: string }
  finish_reason: string
}

interface OllamaChatResponse {
  choices: OllamaChoice[]
  usage?: { prompt_tokens: number; completion_tokens: number }
}

export class OllamaLLMClient implements ILLMClient {
  readonly vendor: LLMVendor = 'ollama'
  readonly modelId: string
  readonly maxTokens: number
  readonly supportsTools = false

  private readonly _baseUrl: string

  constructor(config: OllamaConfig = {}) {
    this.modelId = config.model ?? 'llama3.3'
    this.maxTokens = config.maxTokens ?? 4096
    this._baseUrl = config.baseUrl ?? 'http://localhost:11434'
  }

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    const response = await fetch(`${this._baseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(this._buildBody(request)),
    })

    if (!response.ok) {
      throw new Error(`Ollama API error: ${response.status} ${response.statusText}`)
    }

    return this._parse(await response.json() as OllamaChatResponse)
  }

  async *stream(request: CompletionRequest): AsyncIterableIterator<CompletionChunk> {
    const response = await fetch(`${this._baseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...this._buildBody(request), stream: true }),
    })

    if (!response.ok || !response.body) {
      throw new Error(`Ollama stream error: ${response.status}`)
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
        } catch { /* skip */ }
      }
    }
    yield { delta: '', done: true }
  }

  private _buildBody(request: CompletionRequest): Record<string, unknown> {
    return {
      model: this.modelId,
      messages: request.messages.map(m => ({ role: m.role, content: m.content })),
      ...(request.maxTokens && { max_tokens: request.maxTokens }),
      ...(request.temperature !== undefined && { temperature: request.temperature }),
    }
  }

  private _parse(data: OllamaChatResponse): CompletionResponse {
    const choice = data.choices[0]
    if (!choice) throw new Error('Ollama returned no choices')
    return {
      content: choice.message.content,
      stopReason: choice.finish_reason === 'length' ? 'max_tokens' : 'end_turn',
      usage: {
        inputTokens: data.usage?.prompt_tokens ?? 0,
        outputTokens: data.usage?.completion_tokens ?? 0,
      },
    }
  }
}
