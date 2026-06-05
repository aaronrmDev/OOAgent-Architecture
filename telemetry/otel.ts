// telemetry/otel.ts — OpenTelemetry ITelemetryProvider adapter
// Optional peer dependency: npm install @opentelemetry/api @opentelemetry/sdk-node
// Without the package installed, this provider silently no-ops.
import { ITelemetryProvider } from '../core/protocols.js'

// Minimal structural types — avoids hard import of the optional OTel package
interface OTelSpan {
  setStatus(status: { code: number; message?: string }): void
  recordException(err: Error): void
  addEvent(name: string, attrs?: Record<string, unknown>): void
  end(): void
}
interface OTelTracer {
  startActiveSpan<T>(name: string, fn: (span: OTelSpan) => Promise<T>): Promise<T>
}
interface OTelCounter { add(delta: number): void }
interface OTelHistogram { record(value: number): void }
interface OTelObservableGauge {} // eslint-disable-line @typescript-eslint/no-empty-object-type
interface OTelMeter {
  createCounter(name: string): OTelCounter
  createHistogram(name: string): OTelHistogram
  createObservableGauge(name: string, cb: (obs: { observe(v: number): void }) => void): OTelObservableGauge
}
interface OTelActiveSpan { addEvent(name: string, attrs?: Record<string, unknown>): void }
interface OTelApi {
  trace: {
    getTracer(name: string): OTelTracer
    getActiveSpan(): OTelActiveSpan | undefined
  }
  metrics: { getMeter(name: string): OTelMeter }
  SpanStatusCode: { OK: number; ERROR: number }
}

async function loadOTelApi(): Promise<OTelApi | null> {
  try {
    // Dynamic require keeps the package optional at compile time
    const mod = await import('@opentelemetry/api' as string) as OTelApi
    return mod
  } catch {
    return null
  }
}

export class OpenTelemetryProvider implements ITelemetryProvider {
  private _otel: OTelApi | null = null
  private readonly _serviceName: string

  constructor(serviceName = 'ooagent') {
    this._serviceName = serviceName
    loadOTelApi().then(api => { this._otel = api }).catch(() => undefined)
  }

  async span<T>(name: string, fn: () => Promise<T>): Promise<T> {
    const otel = this._otel
    if (!otel) return fn()

    const tracer = otel.trace.getTracer(this._serviceName)
    return tracer.startActiveSpan(name, async (span: OTelSpan) => {
      try {
        const result = await fn()
        span.setStatus({ code: otel.SpanStatusCode.OK })
        return result
      } catch (err) {
        span.setStatus({ code: otel.SpanStatusCode.ERROR, message: (err as Error).message })
        span.recordException(err as Error)
        throw err
      } finally {
        span.end()
      }
    })
  }

  counter(name: string, delta = 1): void {
    const otel = this._otel
    if (!otel) return
    otel.metrics.getMeter(this._serviceName).createCounter(name).add(delta)
  }

  gauge(name: string, value: number): void {
    const otel = this._otel
    if (!otel) return
    otel.metrics.getMeter(this._serviceName).createObservableGauge(name, obs => obs.observe(value))
  }

  histogram(name: string, value: number): void {
    const otel = this._otel
    if (!otel) return
    otel.metrics.getMeter(this._serviceName).createHistogram(name).record(value)
  }

  event(name: string, payload: Record<string, unknown>): void {
    const otel = this._otel
    if (!otel) return
    otel.trace.getActiveSpan()?.addEvent(name, payload)
  }
}
