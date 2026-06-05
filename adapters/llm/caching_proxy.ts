// adapters/llm/caching_proxy.ts — CachingLLMProxy and ThrottlingLLMProxy (Proxy pattern)
import {
  CompletionChunk,
  CompletionRequest,
  CompletionResponse,
  ILLMClient,
  LLMVendor,
} from '../../core/protocols.js'

// Proxy — caches deterministic completions — §4 GoF
export class CachingLLMProxy implements ILLMClient {
  private readonly _cache = new Map<string, CompletionResponse>()

  constructor(private readonly _inner: ILLMClient) {}

  get vendor(): LLMVendor { return this._inner.vendor }
  get modelId(): string { return this._inner.modelId }
  get maxTokens(): number { return this._inner.maxTokens }
  get supportsTools(): boolean { return this._inner.supportsTools }

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    // Only cache deterministic requests (no tools, temperature 0 or unset)
    const cacheable = !request.tools?.length && (request.temperature ?? 0) === 0
    if (!cacheable) return this._inner.complete(request)

    const key = this._cacheKey(request)
    const cached = this._cache.get(key)
    if (cached) return cached

    const result = await this._inner.complete(request)
    this._cache.set(key, result)
    return result
  }

  async *stream(request: CompletionRequest): AsyncIterableIterator<CompletionChunk> {
    yield* this._inner.stream(request)
  }

  clearCache(): void { this._cache.clear() }
  get cacheSize(): number { return this._cache.size }

  private _cacheKey(request: CompletionRequest): string {
    return JSON.stringify({
      model: this._inner.modelId,
      messages: request.messages,
      maxTokens: request.maxTokens,
    })
  }
}

// Proxy — enforces rate limits transparently — §4 GoF
export class ThrottlingLLMProxy implements ILLMClient {
  private _tokens: number
  private _lastRefill: number

  constructor(
    private readonly _inner: ILLMClient,
    private readonly _options: {
      requestsPerMinute: number
    },
  ) {
    this._tokens = _options.requestsPerMinute
    this._lastRefill = Date.now()
  }

  get vendor(): LLMVendor { return this._inner.vendor }
  get modelId(): string { return this._inner.modelId }
  get maxTokens(): number { return this._inner.maxTokens }
  get supportsTools(): boolean { return this._inner.supportsTools }

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    await this._throttle()
    return this._inner.complete(request)
  }

  async *stream(request: CompletionRequest): AsyncIterableIterator<CompletionChunk> {
    await this._throttle()
    yield* this._inner.stream(request)
  }

  private async _throttle(): Promise<void> {
    this._refill()
    if (this._tokens <= 0) {
      const msPerToken = 60_000 / this._options.requestsPerMinute
      await new Promise<void>(resolve => setTimeout(resolve, msPerToken))
      this._refill()
    }
    this._tokens--
  }

  private _refill(): void {
    const now = Date.now()
    const elapsed = now - this._lastRefill
    const refill = Math.floor((elapsed / 60_000) * this._options.requestsPerMinute)
    if (refill > 0) {
      this._tokens = Math.min(this._options.requestsPerMinute, this._tokens + refill)
      this._lastRefill = now
    }
  }
}
