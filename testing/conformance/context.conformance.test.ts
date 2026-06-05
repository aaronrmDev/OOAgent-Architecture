// testing/conformance/context.conformance.test.ts
// IDomainContext conformance suite — §17 CLAUDE.md
import { describe, test } from 'node:test'
import { strictEqual, ok, doesNotThrow } from 'node:assert'
import type {
  AntiPattern,
  ArtifactPolicy,
  IDomainContext,
  Invariant,
  ISolver,
  InputSpec,
  PipelineStep,
  ProblemClass,
  Query,
  Term,
} from '../../core/protocols.js'

// Minimal conformant IDomainContext for conformance testing
class StubDomainContext implements IDomainContext {
  readonly name    = 'StubConformance'
  readonly version = '1.0.0'

  vocabulary(): Set<Term> {
    return new Set([{ label: 'stub-term', definition: 'A test term', canonical: true }])
  }

  problemClasses(): Set<ProblemClass> {
    return new Set([{
      name: 'StubProblem', description: 'Stub problem class', solver: 'stub',
    }])
  }

  solvers(): Map<string, ISolver> { return new Map() }

  invariants(): Invariant[] {
    return [{ name: 'stub-invariant', condition: 'true', severity: 'error', rationale: 'test' }]
  }

  antiPatterns(): AntiPattern[] { return [] }

  requiredInputs(_pc: ProblemClass): InputSpec[] { return [] }

  resolveIntent(_q: Query): ProblemClass | null { return null }

  artifactPreferences(): ArtifactPolicy {
    return { preferredFormats: ['text', 'json'], typeHintsRequired: true, commentPolicy: 'none' }
  }

  systemPromptExtension(): string { return 'Stub context active.' }

  pipeline(): PipelineStep[] { return [] }
}

const ctx: IDomainContext = new StubDomainContext()
const nullQuery: Query = { text: '', format: 'text', metadata: {} }

describe('IDomainContext conformance (§17 CLAUDE.md)', () => {
  test('vocabulary() returns non-empty Set of Terms', () => {
    const vocab = ctx.vocabulary()
    ok(vocab.size > 0, 'vocabulary() must return a non-empty set')
  })

  test('problemClasses() returns non-empty Set of ProblemClass', () => {
    const classes = ctx.problemClasses()
    ok(classes.size > 0, 'problemClasses() must return a non-empty set')
  })

  test('invariants() are callable without throwing', () => {
    doesNotThrow(() => ctx.invariants(), 'invariants() must not throw')
    ok(Array.isArray(ctx.invariants()), 'invariants() must return an array')
  })

  test('resolveIntent returns null for unrecognized (null-equivalent) query', () => {
    const result = ctx.resolveIntent(nullQuery)
    strictEqual(result, null, 'resolveIntent must return null for unrecognized queries — not throw')
  })

  test('artifactPreferences().preferredFormats is non-empty', () => {
    const prefs = ctx.artifactPreferences()
    ok(prefs.preferredFormats.length > 0, 'artifactPreferences().preferredFormats must be non-empty')
  })
})
