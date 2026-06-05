// plugins/logging/index.ts — LoggingPlugin
// Contributes a ResponseDecorator that appends a provenance/log footer to every artifact.
import {
  Artifact,
  IAgent,
  PluginContributions,
  ProvenanceRecord,
  ResponseDecoratorFn,
} from '../../core/protocols.js'
import { AbstractPlugin } from '../base-plugin.js'

export interface LoggingPluginOptions {
  /** Prefix written before each log line. Default: '[OOAgent]' */
  prefix?: string
  /** Whether to include full provenance records in the footer. Default: true */
  includeProvenance?: boolean
  /** Custom sink — defaults to console.log */
  sink?: (line: string) => void
}

export class LoggingPlugin extends AbstractPlugin {
  readonly pluginId = 'ooagent.logging'
  readonly version  = '1.0.0'

  private readonly _prefix: string
  private readonly _includeProvenance: boolean
  private readonly _sink: (line: string) => void
  private _agentId = '<unregistered>'

  constructor(opts: LoggingPluginOptions = {}) {
    super()
    this._prefix            = opts.prefix            ?? '[OOAgent]'
    this._includeProvenance = opts.includeProvenance ?? true
    this._sink              = opts.sink              ?? ((l: string) => console.log(l))
  }

  override onRegister(agent: IAgent<unknown, unknown>): void {
    this._agentId = agent.agentId
    this._sink(`${this._prefix} LoggingPlugin registered on agent ${this._agentId}`)
  }

  override onDispose(): void {
    this._sink(`${this._prefix} LoggingPlugin disposed for agent ${this._agentId}`)
  }

  override contributes(): PluginContributions {
    return { decorators: [this._buildDecorator()] }
  }

  private _buildDecorator(): ResponseDecoratorFn {
    const prefix = this._prefix
    const includeProvenance = this._includeProvenance
    const sink = this._sink

    return (artifact: Artifact, provenance: ProvenanceRecord[]): Artifact => {
      const timestamp = new Date().toISOString()
      sink(`${prefix} [${timestamp}] turn complete — format=${artifact.format}`)

      if (!includeProvenance || provenance.length === 0) {
        return artifact
      }

      const footer = provenance
        .map(p => `<!-- source: ${p.source} [${p.tag}] -->`)
        .join('\n')

      return {
        ...artifact,
        content: `${artifact.content}\n\n${footer}`,
      }
    }
  }
}
