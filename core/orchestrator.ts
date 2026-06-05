// core/orchestrator.ts — MultiAgentOrchestrator, SignalBus
import {
  ArtifactFormat,
  IDomainContext,
  IOrchestrator,
  Query,
  Solution,
} from './protocols.js'

type SignalHandler<T> = (payload: T) => void

// Mediator — collaborators communicate only through SignalBus — §4 GoF
export class SignalBus {
  private readonly _handlers = new Map<string, Set<SignalHandler<unknown>>>()

  publish<T>(signal: string, payload: T): void {
    const handlers = this._handlers.get(signal)
    if (!handlers) return
    for (const handler of handlers) {
      try {
        handler(payload)
      } catch (err) {
        console.error(`[SignalBus] Handler error for signal "${signal}":`, err)
      }
    }
  }

  subscribe<T>(signal: string, handler: SignalHandler<T>): () => void {
    if (!this._handlers.has(signal)) {
      this._handlers.set(signal, new Set())
    }
    this._handlers.get(signal)!.add(handler as SignalHandler<unknown>)
    return () => { this._handlers.get(signal)?.delete(handler as SignalHandler<unknown>) }
  }
}

// Semaphore — bounds parallel API calls — §13 CLAUDE.md
class Semaphore {
  private _running = 0
  private readonly _queue: Array<() => void> = []

  constructor(private readonly _limit: number) {}

  async run<T>(fn: () => Promise<T>): Promise<T> {
    await this._acquire()
    try {
      return await fn()
    } finally {
      this._release()
    }
  }

  private _acquire(): Promise<void> {
    if (this._running < this._limit) {
      this._running++
      return Promise.resolve()
    }
    return new Promise(resolve => {
      this._queue.push(() => { this._running++; resolve() })
    })
  }

  private _release(): void {
    this._running--
    const next = this._queue.shift()
    if (next) next()
  }
}

export type SpecialistAgentFactory = (
  context: IDomainContext,
) => { respond(q: Query): Promise<unknown> }

// Multi-agent orchestration — §13 CLAUDE.md
export class MultiAgentOrchestrator implements IOrchestrator {
  private readonly _bus = new SignalBus()
  private readonly _semaphore: Semaphore

  constructor(
    private readonly _agentFactory: SpecialistAgentFactory,
    options: { concurrency?: number } = {},
  ) {
    this._semaphore = new Semaphore(options.concurrency ?? 5)
  }

  get bus(): SignalBus { return this._bus }

  async dispatch(query: Query, contexts: IDomainContext[]): Promise<Solution[]> {
    return Promise.all(
      contexts.map(ctx =>
        this._semaphore.run(() => this._runSpecialist(query, ctx)),
      ),
    )
  }

  async synthesize(solutions: Solution[], _original: Query): Promise<Solution> {
    // Default: concatenate. Override with a meta-agent LLM call when available.
    const content = solutions.map(s => s.content).join('\n\n---\n\n')
    return {
      content,
      format: 'text' as ArtifactFormat,
      sources: solutions.flatMap(s => s.sources),
    }
  }

  private async _runSpecialist(query: Query, ctx: IDomainContext): Promise<Solution> {
    try {
      const agent = this._agentFactory(ctx)
      const raw = await agent.respond(query)
      const solution: Solution = {
        content: typeof raw === 'string' ? raw : JSON.stringify(raw),
        format: 'text' as ArtifactFormat,
        sources: [],
      }
      this._bus.publish<{ context: string; solution: Solution }>('specialist.done', {
        context: ctx.name,
        solution,
      })
      return solution
    } catch (err) {
      return {
        content: `[SpecialistError] ${ctx.name}: ${(err as Error).message}`,
        format: 'text' as ArtifactFormat,
        sources: [],
      }
    }
  }
}
