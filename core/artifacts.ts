// core/artifacts.ts — ArtifactFactory, ProvenanceTracker, ResponseDecorator
import {
  Artifact,
  ArtifactFormat,
  ArtifactPolicy,
  IArtifactFactory,
  InputSpec,
  ProvenanceRecord,
  ResponseDecoratorFn,
  Solution,
  SourceTag,
} from './protocols.js'

type ArtifactBuilder = (solution: Solution, policy: ArtifactPolicy) => string

// Factory Method — dispatches to format-specific builders — §4 GoF
export class ArtifactFactory implements IArtifactFactory {
  private readonly _builders = new Map<ArtifactFormat, ArtifactBuilder>()

  registerBuilder(format: ArtifactFormat, builder: ArtifactBuilder): void {
    this._builders.set(format, builder)
  }

  build(solution: Solution, format: ArtifactFormat, policy: ArtifactPolicy): Artifact {
    const builder = this._builders.get(format)
    const content = builder ? builder(solution, policy) : solution.content
    return {
      content,
      format,
      provenance: solution.sources.map(s => ({
        source: s.ref,
        tag: s.tag,
        timestamp: Date.now(),
      })),
      metadata: solution.metadata,
    }
  }

  buildError(violation: string, ctx: string): Artifact {
    return {
      content: `[ConstraintViolation]\nContext: ${ctx}\n\n${violation}`,
      format: 'text',
      provenance: [],
    }
  }

  buildMissingInputs(missing: InputSpec[], ctx: string): Artifact {
    const list = missing
      .map((inp, i) => `${i + 1}. **${inp.name}** (${inp.type}): ${inp.description}`)
      .join('\n')
    return {
      content: `[MissingInputs]\nContext: ${ctx}\n\nRequired inputs:\n${list}`,
      format: 'md',
      provenance: [],
    }
  }

  buildScopeExit(ctx: string, query: string): Artifact {
    return {
      content: `[ScopeExit]\nContext: ${ctx}\nQuery: "${query}"\n\nThis query is out of scope for the active context.`,
      format: 'text',
      provenance: [],
    }
  }
}

// Pure Fabrication — source / citation discipline — §3 GRASP
export class ProvenanceTracker {
  private _records: ProvenanceRecord[] = []

  record(source: string, tag: SourceTag): void {
    this._records.push({ source, tag, timestamp: Date.now() })
  }

  dump(): ProvenanceRecord[] {
    return [...this._records]
  }

  clear(): void {
    this._records = []
  }
}

// Decorator — appends citations, units, provenance after solving — §4 GoF
export class ResponseDecorator {
  private readonly _fns: ResponseDecoratorFn[]

  constructor(fns: ResponseDecoratorFn[] = []) {
    this._fns = [...fns]
  }

  addDecorator(fn: ResponseDecoratorFn): void {
    this._fns.push(fn)
  }

  apply(artifact: Artifact, provenance: ProvenanceRecord[]): Artifact {
    return this._fns.reduce((acc, fn) => fn(acc, provenance), artifact)
  }
}
