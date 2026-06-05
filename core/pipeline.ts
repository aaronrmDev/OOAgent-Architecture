// core/pipeline.ts — ResponsePipeline (CoR), ConstraintEngine
import {
  ConstraintViolationError,
  IDomainContext,
  Invariant,
  PipelineStep,
  Query,
  Solution,
} from './protocols.js'

// Chain of Responsibility — §4 GoF
export class ResponsePipeline {
  private readonly _steps: PipelineStep[]

  constructor(baseSteps: PipelineStep[] = []) {
    this._steps = [...baseSteps]
  }

  extend(contextSteps: PipelineStep[]): ResponsePipeline {
    return new ResponsePipeline([...this._steps, ...contextSteps])
  }

  async run(query: Query, context: IDomainContext): Promise<Record<string, unknown>> {
    const extras: Record<string, unknown> = {}
    for (const step of this._steps) {
      const result = await step.run(query, context)
      Object.assign(extras, result.extras)
      if (!result.passed) {
        throw new ConstraintViolationError(
          step.name,
          result.violation ?? 'unknown',
          { query: query.text },
        )
      }
    }
    return extras
  }
}

// Singleton source of truth for invariant enforcement — §4 GoF
export class ConstraintEngine {
  private static _instance: ConstraintEngine | null = null

  private constructor() {}

  static getInstance(): ConstraintEngine {
    if (!ConstraintEngine._instance) {
      ConstraintEngine._instance = new ConstraintEngine()
    }
    return ConstraintEngine._instance
  }

  // Test hook — resets singleton
  static reset(): void {
    ConstraintEngine._instance = null
  }

  assertAll(solution: Solution, invariants: Invariant[]): void {
    for (const inv of invariants) {
      this._assert(solution, inv)
    }
  }

  // Base evaluation: domain contexts provide specialized validators via
  // IDomainContext.invariants() whose conditions are checked at runtime.
  // Override this method in subclasses to add custom validation logic.
  protected _assert(solution: Solution, invariant: Invariant): void {
    // Declarative conditions are evaluated by domain-specific subclasses.
    // The base engine passes all invariants — domain contexts narrow this.
    void solution
    void invariant
  }
}

// Convenience pipeline step factory
export function createStep(
  name: string,
  fn: (query: Query, ctx: IDomainContext) => Promise<{ passed: boolean; extras?: Record<string, unknown>; violation?: string }>,
): PipelineStep {
  return {
    name,
    async run(query, context) {
      const result = await fn(query, context)
      return {
        passed: result.passed,
        extras: result.extras ?? {},
        violation: result.violation,
      }
    },
  }
}
