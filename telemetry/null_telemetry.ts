// telemetry/null_telemetry.ts — NullTelemetry (Null Object — default for unit tests)
import { ITelemetryProvider } from '../core/protocols.js'

export class NullTelemetry implements ITelemetryProvider {
  async span<T>(_name: string, fn: () => Promise<T>): Promise<T> {
    return fn()
  }
  counter(_name: string, _delta?: number): void {}
  gauge(_name: string, _value: number): void {}
  histogram(_name: string, _value: number): void {}
  event(_name: string, _payload: Record<string, unknown>): void {}
}
