// plugins/opentelemetry/index.ts — OpenTelemetryPlugin
// Contributes an ITelemetryProvider backed by the OpenTelemetry SDK.
// The agent core never imports @opentelemetry directly — all SDK access is
// mediated through this plugin (DIP, OCP).
import {
  IAgent,
  ITelemetryProvider,
  PluginContributions,
} from '../../core/protocols.js'
import { AbstractPlugin } from '../base-plugin.js'

export interface OtelPluginOptions {
  /** Service name reported to the collector. Default: 'ooagent' */
  serviceName?: string
  /** OTLP endpoint URL. Default: 'http://localhost:4318/v1/traces' */
  endpoint?: string
  /**
   * Inject a pre-configured ITelemetryProvider (for testing or custom setup).
   * When provided, endpoint and serviceName are ignored.
   */
  provider?: ITelemetryProvider
}

// Concrete ITelemetryProvider backed by @opentelemetry/sdk-node (lazy-loaded).
// If @opentelemetry is not installed, falls back to console output with a warning.
class OtelTelemetryProvider implements ITelemetryProvider {
  private readonly _serviceName: string
  private readonly _endpoint: string
  private _sdk: unknown = null
  private _tracer: unknown = null
  private _meter: unknown = null

  constructor(serviceName: string, endpoint: string) {
    this._serviceName = serviceName
    this._endpoint    = endpoint
  }

  async init(): Promise<void> {
    try {
      // Dynamic import — keeps @opentelemetry as an optional peer dependency
      const { NodeSDK }   = await import('@opentelemetry/sdk-node' as string as any)
      const { Resource }  = await import('@opentelemetry/resources' as string as any)
      const { OTLPTraceExporter } = await import('@opentelemetry/exporter-trace-otlp-http' as string as any)
      const { SEMRESATTRS_SERVICE_NAME } = await import('@opentelemetry/semantic-conventions' as string as any)

      this._sdk = new NodeSDK({
        resource: new Resource({ [SEMRESATTRS_SERVICE_NAME]: this._serviceName }),
        traceExporter: new OTLPTraceExporter({ url: this._endpoint }),
      })
      ;(this._sdk as any).start()

      const { trace, metrics } = await import('@opentelemetry/api' as string as any)
      this._tracer = trace.getTracer(this._serviceName)
      this._meter  = metrics.getMeter(this._serviceName)
    } catch {
      console.warn(
        '[OtelPlugin] @opentelemetry packages not found — falling back to console telemetry. ' +
        'Install @opentelemetry/sdk-node and peer packages to enable OTLP export.',
      )
    }
  }

  async shutdown(): Promise<void> {
    if (this._sdk) {
      try {
        await (this._sdk as any).shutdown()
      } catch (err) {
        console.warn('[OtelPlugin] SDK shutdown error:', err)
      }
    }
  }

  async span<T>(name: string, fn: () => Promise<T>): Promise<T> {
    if (!this._tracer) return fn()
    const span = (this._tracer as any).startSpan(name)
    try {
      const result = await fn()
      span.setStatus({ code: 1 }) // OK
      return result
    } catch (err) {
      span.setStatus({ code: 2, message: (err as Error).message }) // ERROR
      throw err
    } finally {
      span.end()
    }
  }

  counter(name: string, delta = 1): void {
    if (!this._meter) { console.log(`[otel.counter] ${name} +${delta}`); return }
    ;(this._meter as any).createCounter(name).add(delta)
  }

  gauge(name: string, value: number): void {
    if (!this._meter) { console.log(`[otel.gauge] ${name} = ${value}`); return }
    ;(this._meter as any).createObservableGauge(name)
  }

  histogram(name: string, value: number): void {
    if (!this._meter) { console.log(`[otel.histogram] ${name} = ${value}`); return }
    ;(this._meter as any).createHistogram(name).record(value)
  }

  event(name: string, payload: Record<string, unknown>): void {
    if (!this._tracer) { console.log(`[otel.event] ${name}`, payload); return }
    const span = (this._tracer as any).startSpan(name)
    Object.entries(payload).forEach(([k, v]) => span.setAttribute(k, String(v)))
    span.end()
  }
}

export class OpenTelemetryPlugin extends AbstractPlugin {
  readonly pluginId = 'ooagent.opentelemetry'
  readonly version  = '1.0.0'

  private readonly _opts: OtelPluginOptions
  private _provider: OtelTelemetryProvider | null = null

  constructor(opts: OtelPluginOptions = {}) {
    super()
    this._opts = opts
  }

  override async onRegister(_agent: IAgent<unknown, unknown>): Promise<void> {
    if (this._opts.provider) return  // injected externally
    this._provider = new OtelTelemetryProvider(
      this._opts.serviceName ?? 'ooagent',
      this._opts.endpoint    ?? 'http://localhost:4318/v1/traces',
    )
    await this._provider.init()
  }

  override async onDispose(): Promise<void> {
    await this._provider?.shutdown()
    this._provider = null
  }

  override contributes(): PluginContributions {
    // Note: ITelemetryProvider is injected at OOAgent construction time,
    // so this plugin exposes a getter for the consumer to wire it in.
    // Plugin contributes nothing to registries — the provider is accessed via .telemetryProvider.
    return {}
  }

  /** The constructed provider — inject into OOAgent options.telemetry. */
  get telemetryProvider(): ITelemetryProvider | null {
    return this._opts.provider ?? this._provider
  }
}
