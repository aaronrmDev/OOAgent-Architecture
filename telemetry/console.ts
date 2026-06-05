// telemetry/console.ts — ConsoleTelemetry for development
import { ITelemetryProvider } from '../core/protocols.js'

export class ConsoleTelemetry implements ITelemetryProvider {
  private readonly _prefix: string

  constructor(prefix = '[Telemetry]') {
    this._prefix = prefix
  }

  async span<T>(name: string, fn: () => Promise<T>): Promise<T> {
    const start = Date.now()
    try {
      const result = await fn()
      console.log(`${this._prefix} span "${name}" completed in ${Date.now() - start}ms`)
      return result
    } catch (err) {
      console.error(`${this._prefix} span "${name}" failed after ${Date.now() - start}ms:`, err)
      throw err
    }
  }

  counter(name: string, delta = 1): void {
    console.log(`${this._prefix} counter "${name}" +${delta}`)
  }

  gauge(name: string, value: number): void {
    console.log(`${this._prefix} gauge "${name}" = ${value}`)
  }

  histogram(name: string, value: number): void {
    console.log(`${this._prefix} histogram "${name}" ${value}`)
  }

  event(name: string, payload: Record<string, unknown>): void {
    console.log(`${this._prefix} event "${name}"`, payload)
  }
}
