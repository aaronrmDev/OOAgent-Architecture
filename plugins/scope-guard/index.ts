// plugins/scope-guard/index.ts — ScopeGuardPlugin
// Contributes an IDomainContext that injects a pipeline step enforcing domain boundaries.
// The step blocks queries that match explicit out-of-scope patterns, emitting a ScopeExitError
// before the SOLVING phase — protecting both cost and quality.
import {
  AntiPattern,
  ArtifactPolicy,
  IDomainContext,
  Invariant,
  IPlugin,
  ISolver,
  InputSpec,
  PipelineStep,
  PipelineStepResult,
  PluginContributions,
  ProblemClass,
  Query,
  ScopeExitError,
  Term,
} from '../../core/protocols.js'
import { AbstractPlugin } from '../base-plugin.js'

export interface ScopeGuardOptions {
  /**
   * Keyword patterns (lowercase) that trigger a scope exit.
   * If the query text contains any of these, the turn is halted.
   */
  blockedPatterns?: string[]
  /**
   * Name of the guard context reported in error artifacts. Default: 'ScopeGuard'
   */
  contextName?: string
}

// A context that contributes only the scope-guard pipeline step
class ScopeGuardContext implements IDomainContext {
  readonly name:    string
  readonly version = '1.0.0'
  private readonly _blocked: string[]

  constructor(name: string, blocked: string[]) {
    this.name     = name
    this._blocked = blocked.map(p => p.toLowerCase())
  }

  vocabulary():       Set<Term>               { return new Set() }
  problemClasses():   Set<ProblemClass>       { return new Set() }
  solvers():          Map<string, ISolver>    { return new Map() }
  invariants():       Invariant[]             { return [] }
  antiPatterns():     AntiPattern[]           { return [] }
  requiredInputs(_pc: ProblemClass): InputSpec[] { return [] }
  resolveIntent(_q: Query): ProblemClass | null  { return null }

  artifactPreferences(): ArtifactPolicy {
    return { preferredFormats: ['text'], typeHintsRequired: false, commentPolicy: 'none' }
  }

  systemPromptExtension(): string {
    return `ScopeGuard is active. The following topics are out of scope: ${this._blocked.join(', ')}.`
  }

  pipeline(): PipelineStep[] {
    const blocked = this._blocked
    const name    = this.name
    return [
      {
        name: 'scope-guard',
        async run(query: Query, _ctx: IDomainContext): Promise<PipelineStepResult> {
          const text = query.text.toLowerCase()
          const hit  = blocked.find(p => text.includes(p))
          if (hit) {
            throw new ScopeExitError(name, query.text)
          }
          return { passed: true, extras: {} }
        },
      },
    ]
  }
}

export class ScopeGuardPlugin extends AbstractPlugin implements IPlugin {
  readonly pluginId = 'ooagent.scope-guard'
  readonly version  = '1.0.0'

  private readonly _context: ScopeGuardContext

  constructor(opts: ScopeGuardOptions = {}) {
    super()
    this._context = new ScopeGuardContext(
      opts.contextName    ?? 'ScopeGuard',
      opts.blockedPatterns ?? [],
    )
  }

  override onDispose(): void {}

  override contributes(): PluginContributions {
    return { contexts: [this._context] }
  }

  /** The underlying guard context — useful for direct inspection in tests. */
  get guardContext(): IDomainContext {
    return this._context
  }
}
