// plugins/audit/index.ts — AuditPlugin
// Contributes a ResponseDecorator that records every completed turn to an append-only audit log.
// The audit log is an in-memory ring buffer (configurable size) plus an optional external sink.
import {
  Artifact,
  IAgent,
  PluginContributions,
  ProvenanceRecord,
  ResponseDecoratorFn,
} from '../../core/protocols.js'
import { AbstractPlugin } from '../base-plugin.js'

export interface AuditEntry {
  readonly turn: number
  readonly agentId: string
  readonly contextName: string
  readonly format: string
  readonly provenanceSources: string[]
  readonly contentLength: number
  readonly timestamp: string
}

export interface AuditPluginOptions {
  /** Max entries kept in the in-memory ring buffer. Default: 1000 */
  maxEntries?: number
  /** External sink for real-time streaming (e.g. write to file, send to SIEM). */
  sink?: (entry: AuditEntry) => void | Promise<void>
}

export class AuditPlugin extends AbstractPlugin {
  readonly pluginId = 'ooagent.audit'
  readonly version  = '1.0.0'

  private readonly _maxEntries: number
  private readonly _sink?: (entry: AuditEntry) => void | Promise<void>
  private readonly _log: AuditEntry[] = []
  private _agentId = '<unregistered>'
  private _turn = 0

  constructor(opts: AuditPluginOptions = {}) {
    super()
    this._maxEntries = opts.maxEntries ?? 1000
    this._sink       = opts.sink
  }

  override onRegister(agent: IAgent<unknown, unknown>): void {
    this._agentId = agent.agentId
  }

  override onDispose(): void {
    this._log.length = 0
  }

  override contributes(): PluginContributions {
    return { decorators: [this._buildDecorator()] }
  }

  /** Immutable snapshot of the audit log. */
  get entries(): readonly AuditEntry[] {
    return Object.freeze([...this._log])
  }

  /** Returns all audit entries for a given context name. */
  entriesForContext(name: string): AuditEntry[] {
    return this._log.filter(e => e.contextName === name)
  }

  private _buildDecorator(): ResponseDecoratorFn {
    return (artifact: Artifact, provenance: ProvenanceRecord[]): Artifact => {
      this._turn += 1
      const entry: AuditEntry = {
        turn:              this._turn,
        agentId:           this._agentId,
        contextName:       artifact.metadata?.['contextName'] as string ?? 'unknown',
        format:            artifact.format,
        provenanceSources: provenance.map(p => `${p.source} [${p.tag}]`),
        contentLength:     artifact.content.length,
        timestamp:         new Date().toISOString(),
      }

      // Ring buffer — evict oldest on overflow
      if (this._log.length >= this._maxEntries) {
        this._log.shift()
      }
      this._log.push(entry)

      // Fire-and-forget to external sink — never let it crash the turn
      if (this._sink) {
        Promise.resolve(this._sink(entry)).catch(err =>
          console.error('[AuditPlugin] Sink error:', err),
        )
      }

      return artifact
    }
  }
}
