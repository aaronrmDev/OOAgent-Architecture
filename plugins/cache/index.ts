// plugins/cache/index.ts — CachePlugin
// Contributes a CachingLLMProxy-compatible tool-level cache.
// Caches deterministic tool results (idempotent tools) by (name, stable-JSON-args).
import {
  ITool,
  JSONSchema,
  LLMVendor,
  PluginContributions,
  VendorToolSpec,
} from '../../core/protocols.js'
import { AbstractPlugin } from '../base-plugin.js'

export interface CachePluginOptions {
  /** Maximum cached entries per tool. Default: 256 */
  maxEntries?: number
  /** TTL for cached entries in milliseconds. Default: 300 000 (5 min) */
  ttlMs?: number
}

interface CacheEntry {
  value: unknown
  expiresAt: number
}

// Wraps an ITool with an in-process LRU-TTL cache for deterministic calls
class CachedTool implements ITool {
  private readonly _cache = new Map<string, CacheEntry>()

  constructor(
    private readonly _inner: ITool,
    private readonly _maxEntries: number,
    private readonly _ttlMs: number,
  ) {}

  get name():        string { return this._inner.name }
  get description(): string { return this._inner.description }
  inputSchema():     JSONSchema        { return this._inner.inputSchema() }
  toVendorSpec(v: LLMVendor): VendorToolSpec { return this._inner.toVendorSpec(v) }

  async execute(args: Record<string, unknown>): Promise<unknown> {
    const key = this._cacheKey(args)
    const now = Date.now()
    const hit = this._cache.get(key)

    if (hit && hit.expiresAt > now) {
      return hit.value
    }

    const result = await this._inner.execute(args)
    this._evictIfNeeded()
    this._cache.set(key, { value: result, expiresAt: now + this._ttlMs })
    return result
  }

  private _cacheKey(args: Record<string, unknown>): string {
    return JSON.stringify(
      Object.keys(args).sort().reduce<Record<string, unknown>>((acc, k) => {
        acc[k] = args[k]
        return acc
      }, {}),
    )
  }

  private _evictIfNeeded(): void {
    if (this._cache.size < this._maxEntries) return
    // Evict oldest entry (insertion-order LRU)
    const oldest = this._cache.keys().next().value
    if (oldest !== undefined) this._cache.delete(oldest)
  }

  /** Clears the entire cache for this tool. */
  flush(): void {
    this._cache.clear()
  }

  get size(): number { return this._cache.size }
}

export class CachePlugin extends AbstractPlugin {
  readonly pluginId = 'ooagent.cache'
  readonly version  = '1.0.0'

  private readonly _maxEntries: number
  private readonly _ttlMs: number
  private _toolsToCache: ITool[] = []
  private _cachedTools: CachedTool[] = []

  constructor(opts: CachePluginOptions = {}) {
    super()
    this._maxEntries = opts.maxEntries ?? 256
    this._ttlMs      = opts.ttlMs      ?? 300_000
  }

  /** Declare which tools should have their results cached. */
  cacheTools(...tools: ITool[]): this {
    this._toolsToCache = tools
    return this
  }

  override onDispose(): void {
    for (const t of this._cachedTools) t.flush()
    this._cachedTools = []
    this._toolsToCache = []
  }

  override contributes(): PluginContributions {
    this._cachedTools = this._toolsToCache.map(
      t => new CachedTool(t, this._maxEntries, this._ttlMs),
    )
    return { tools: this._cachedTools }
  }

  /** Flush all caches. Useful in tests or after context switches. */
  flushAll(): void {
    for (const t of this._cachedTools) t.flush()
  }

  /** Returns the total number of cached entries across all tools. */
  get totalCachedEntries(): number {
    return this._cachedTools.reduce((sum, t) => sum + t.size, 0)
  }
}
