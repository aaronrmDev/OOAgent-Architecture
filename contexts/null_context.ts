// contexts/null_context.ts — NullContext (Null Object pattern)
// Answers safely when no domain is loaded — §4 GoF, §9 CLAUDE.md
import {
  ArtifactPolicy,
  IDomainContext,
  InputSpec,
  Invariant,
  AntiPattern,
  ISolver,
  PipelineStep,
  ProblemClass,
  Query,
  Term,
} from '../core/protocols.js'

export class NullContext implements IDomainContext {
  readonly name = 'NullContext'
  readonly version = '1.0'

  vocabulary(): Set<Term> { return new Set() }
  problemClasses(): Set<ProblemClass> { return new Set() }
  solvers(): Map<string, ISolver> { return new Map() }
  invariants(): Invariant[] { return [] }
  pipeline(): PipelineStep[] { return [] }
  antiPatterns(): AntiPattern[] { return [] }
  requiredInputs(_pc: ProblemClass): InputSpec[] { return [] }

  artifactPreferences(): ArtifactPolicy {
    return {
      preferredFormats: ['text'],
      typeHintsRequired: false,
      commentPolicy: 'none',
    }
  }

  systemPromptExtension(): string {
    return (
      'NullContext v1.0 is active. No domain context has been loaded. ' +
      'Do not make domain-specific claims. ' +
      'If the user asks domain questions, state which context is active and what is unavailable.'
    )
  }

  resolveIntent(_query: Query): ProblemClass | null { return null }
}
