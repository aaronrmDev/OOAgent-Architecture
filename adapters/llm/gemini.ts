// adapters/llm/gemini.ts — ILLMClient → Google Gemini API
import {
  CompletionChunk,
  CompletionRequest,
  CompletionResponse,
  ILLMClient,
  LLMVendor,
  TokenLimitError,
} from '../../core/protocols.js'

export interface GeminiConfig {
  apiKey: string
  model?: string
  maxTokens?: number
  baseUrl?: string
}

interface GeminiPart { text?: string }
interface GeminiContent { role: string; parts: GeminiPart[] }
interface GeminiCandidate {
  content: GeminiContent
  finishReason: string
}
interface GeminiResponse {
  candidates?: GeminiCandidate[]
  usageMetadata?: { promptTokenCount: number; candidatesTokenCount: number }
}

export class GeminiLLMClient implements ILLMClient {
  readonly vendor: LLMVendor = 'gemini'
  readonly modelId: string
  readonly maxTokens: number
  readonly supportsTools = true

  private readonly _apiKey: string
  private readonly _baseUrl: string

  constructor(config: GeminiConfig) {
    this._apiKey = config.apiKey
    this.modelId = config.model ?? 'gemini-1.5-pro'
    this.maxTokens = config.maxTokens ?? 8192
    this._baseUrl = config.baseUrl ?? 'https://generativelanguage.googleapis.com'
  }

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    if (this._estimateTokens(request) > this.maxTokens) {
      throw new TokenLimitError(this._estimateTokens(request), this.maxTokens)
    }

    const url = `${this._baseUrl}/v1beta/models/${this.modelId}:generateContent?key=${this._apiKey}`
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(this._buildBody(request)),
    })

    if (!response.ok) {
      throw new Error(`Gemini API error: ${response.status} ${response.statusText}`)
    }

    return this._parse(await response.json() as GeminiResponse)
  }

  async *stream(request: CompletionRequest): AsyncIterableIterator<CompletionChunk> {
    const url =
      `${this._baseUrl}/v1beta/models/${this.modelId}:streamGenerateContent?key=${this._apiKey}&alt=sse`
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(this._buildBody(request)),
    })

    if (!response.ok || !response.body) {
      throw new Error(`Gemini stream error: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value)
      for (const line of text.split('\n').filter(l => l.startsWith('data: '))) {
        try {
          const event = JSON.parse(line.slice(6)) as GeminiResponse
          const part = event.candidates?.[0]?.content?.parts?.[0]?.text
          if (part) yield { delta: part, done: false }
        } catch { /* skip malformed events */ }
      }
    }
    yield { delta: '', done: true }
  }

  private _buildBody(request: CompletionRequest): Record<string, unknown> {
    const systemMsg = request.messages.find(m => m.role === 'system')
    const userMessages = request.messages.filter(m => m.role !== 'system')

    const contents = userMessages.map(m => ({
      role: m.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: m.content }],
    }))

    const body: Record<string, unknown> = {
      contents,
      generationConfig: {
        maxOutputTokens: request.maxTokens ?? this.maxTokens,
        ...(request.temperature !== undefined && { temperature: request.temperature }),
        ...(request.stopSequences?.length && { stopSequences: request.stopSequences }),
      },
    }
    if (systemMsg) {
      body['systemInstruction'] = { parts: [{ text: systemMsg.content }] }
    }
    if (request.tools?.length) {
      body['tools'] = request.tools
    }
    return body
  }

  private _parse(data: GeminiResponse): CompletionResponse {
    const candidate = data.candidates?.[0]
    const text = candidate?.content?.parts?.map(p => p.text ?? '').join('') ?? ''
    return {
      content: text,
      stopReason: candidate?.finishReason === 'MAX_TOKENS' ? 'max_tokens' : 'end_turn',
      usage: {
        inputTokens: data.usageMetadata?.promptTokenCount ?? 0,
        outputTokens: data.usageMetadata?.candidatesTokenCount ?? 0,
      },
    }
  }

  private _estimateTokens(request: CompletionRequest): number {
    return Math.ceil(request.messages.reduce((s, m) => s + m.content.length, 0) / 4)
  }
}
