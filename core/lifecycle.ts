// core/lifecycle.ts — LifecycleManager, CircuitBreaker
import {
  HealthStatus,
  IAgentConfig,
  ILifecycle,
  LifecycleError,
} from './protocols.js'
import { PluginRegistry } from './registry.js'
import { SessionState } from './state.js'

// Circuit breaker — degrades after N consecutive failures — §6 CLAUDE.md
export class CircuitBreaker {
  private _failures = 0
  private _open = false

  constructor(private readonly _threshold: number) {}

  get isOpen(): boolean { return this._open }

  recordSuccess(): void {
    this._failures = 0
    this._open = false
  }

  recordFailure(): void {
    this._failures += 1
    if (this._failures >= this._threshold) {
      this._open = true
    }
  }

  reset(): void {
    this._failures = 0
    this._open = false
  }
}

export class LifecycleManager implements ILifecycle {
  private _ready = false
  private _disposed = false
  private _circuitBreaker: CircuitBreaker | null = null
  private _exitHandlerRegistered = false

  constructor(
    private readonly _pluginRegistry: PluginRegistry,
    private readonly _state: SessionState,
  ) {}

  // Ordered initialization — §6 CLAUDE.md
  async initialize(config: IAgentConfig): Promise<void> {
    if (this._disposed) {
      throw new LifecycleError('Cannot initialize a disposed agent')
    }
    if (this._ready) return

    this._circuitBreaker = new CircuitBreaker(config.circuitBreakerThreshold)
    this._pluginRegistry.verify()
    this._ready = true

    if (!this._exitHandlerRegistered) {
      this._registerExitHandlers()
      this._exitHandlerRegistered = true
    }
  }

  async healthCheck(): Promise<HealthStatus> {
    if (!this._ready) return 'unhealthy'
    if (this._circuitBreaker?.isOpen) return 'degraded'
    return 'healthy'
  }

  // Graceful dispose — §6 CLAUDE.md
  async dispose(): Promise<void> {
    if (!this._ready) {
      throw new LifecycleError('Cannot dispose an uninitialized agent')
    }
    await this._pluginRegistry.disposeAll()
    await this._state.flush()
    this._ready = false
    this._disposed = true
  }

  get isReady(): boolean { return this._ready }

  recordLLMSuccess(): void { this._circuitBreaker?.recordSuccess() }
  recordLLMFailure(): void { this._circuitBreaker?.recordFailure() }

  private _registerExitHandlers(): void {
    if (typeof process === 'undefined') return
    const handler = () => {
      if (this._ready) {
        this.dispose().catch(err => console.error('[LifecycleManager] Dispose error:', err))
      }
    }
    process.once('exit', handler)
    process.once('SIGINT', handler)
    process.once('SIGTERM', handler)
  }
}
