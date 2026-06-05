// core/agent.ts — AbstractAgent, LLMAgent, OOAgent (composition root, Template Method)
import { randomUUID } from 'node:crypto'
import {
  Artifact,
  ArtifactFormat,
  Command,
  CompletionRequest,
  ConstraintViolationError,
  IAgent,
  IAgentConfig,
  IDomainContext,
  ILLMClient,
  ISessionState,
  ITelemetryProvider,
  LifecycleError,
  Message,
  Query,
  ScopeExitError,
  Solution,
  ToolCall,
} from './protocols.js'
import { ArtifactFactory, ProvenanceTracker, ResponseDecorator } from './artifacts.js'
import { ConstraintEngine, ResponsePipeline } from './pipeline.js'
import { ContextRegistry, PluginRegistry, ToolRegistry } from './registry.js'
import { LifecycleManager } from './lifecycle.js'
import { SessionState } from './state.js'

// ── Strategy: solver dispatch — selects ISolver per ProblemClass ──────────────
class SolverDispatcher {
  select(problemClass: string, context: IDomainContext) {
    return context.solvers().get(problemClass) ?? null
  }
}

// ── Abstract base — root interface implementation ─────────────────────────────
export abstract class AbstractAgent<TQuery, TResponse>
  implements IAgent<TQuery, TResponse>
{
  readonly agentId: string
  abstract readonly state: ISessionState

  constructor(id: string = randomUUID()) {
    this.agentId = id
  }

  abstract respond(query: TQuery): Promise<TResponse>
}

// ── LLM-backed abstract — adds ILLMClient ────────────────────────────────────
export abstract class LLMAgent<TQuery, TResponse>
  extends AbstractAgent<TQuery, TResponse>
{
  constructor(
    protected readonly _llmClient: ILLMClient,
    id?: string,
  ) {
    super(id)
  }
}

// ── OOAgent — concrete composition root ──────────────────────────────────────
export class OOAgent extends LLMAgent<Query, Artifact> {
  readonly state: SessionState

  private readonly _lifecycle: LifecycleManager
  private readonly _ctxRegistry: ContextRegistry
  private readonly _toolRegistry: ToolRegistry
  private readonly _pluginRegistry: PluginRegistry
  private readonly _pipeline: ResponsePipeline
  private readonly _constraintEngine: ConstraintEngine
  private readonly _artifactFactory: ArtifactFactory
  private readonly _decorator: ResponseDecorator
  private readonly _provenance: ProvenanceTracker
  private readonly _solverDispatcher = new SolverDispatcher()
  private readonly _telemetry: ITelemetryProvider
  private _config: IAgentConfig | null = null

  constructor(
    llmClient: ILLMClient,
    options: {
      ctxRegistry?: ContextRegistry
      toolRegistry?: ToolRegistry
      pluginRegistry?: PluginRegistry
      pipeline?: ResponsePipeline
      artifactFactory?: ArtifactFactory
      decorator?: ResponseDecorator
      telemetry?: ITelemetryProvider
      id?: string
    } = {},
  ) {
    super(llmClient, options.id)
    this.state = new SessionState()
    this._ctxRegistry = options.ctxRegistry ?? ContextRegistry.getInstance()
    this._toolRegistry = options.toolRegistry ?? new ToolRegistry()
    this._pluginRegistry = options.pluginRegistry ?? new PluginRegistry()
    this._pipeline = options.pipeline ?? new ResponsePipeline()
    this._constraintEngine = ConstraintEngine.getInstance()
    this._artifactFactory = options.artifactFactory ?? new ArtifactFactory()
    this._decorator = options.decorator ?? new ResponseDecorator()
    this._provenance = new ProvenanceTracker()
    this._telemetry = options.telemetry ?? NULL_TELEMETRY
    this._lifecycle = new LifecycleManager(this._pluginRegistry, this.state)
  }

  get isReady(): boolean { return this._lifecycle.isReady }

  async initialize(config: IAgentConfig): Promise<void> {
    this._config = config
    await this._lifecycle.initialize(config)

    for (const plugin of this._pluginRegistry.all()) {
      try {
        plugin.onRegister(this)
        const contributions = plugin.contributes()
        for (const tool of contributions.tools ?? []) {
          this._toolRegistry.register(tool)
        }
        for (const ctx of contributions.contexts ?? []) {
          this._ctxRegistry.register(ctx)
        }
        for (const dec of contributions.decorators ?? []) {
          this._decorator.addDecorator(dec)
        }
      } catch (err) {
        console.error(`[OOAgent] Plugin registration failed: ${plugin.pluginId}`, err)
      }
    }
  }

  async dispose(): Promise<void> {
    await this._lifecycle.dispose()
  }

  // Template Method — §10 CLAUDE.md
  async respond(query: Query): Promise<Artifact> {
    if (!this._lifecycle.isReady) {
      throw new LifecycleError('Agent is not ready. Call initialize() first.')
    }

    return this._telemetry.span('agent.turn', async () => {
      this._provenance.clear()
      this.state.transition('GATHERING')

      const context = this._ctxRegistry.resolve(query)
      this.state.setContext(context.name)
      const pipeline = this._pipeline.extend(context.pipeline())
      const snapshot = this.state.snapshot()

      // MODELING — validate query through CoR pipeline
      this.state.transition('MODELING')
      let extras: Record<string, unknown> = {}
      try {
        extras = await pipeline.run(query, context)
      } catch (err) {
        return this._handleFailure(err, context, snapshot.id)
      }

      // SOLVING — LLM + tool loop, with solver dispatch
      this.state.transition('SOLVING')
      let solution: Solution
      try {
        solution = await this._solve(query, context, extras)
      } catch (err) {
        return this._handleFailure(err, context, snapshot.id)
      }

      // VALIDATING — domain invariants
      this.state.transition('VALIDATING')
      try {
        this._constraintEngine.assertAll(solution, context.invariants())
      } catch (err) {
        return this._handleFailure(err, context, snapshot.id)
      }

      // DELIVERING — build + decorate
      this.state.transition('DELIVERING')
      const format: ArtifactFormat =
        query.format ?? context.artifactPreferences().preferredFormats[0] ?? 'text'
      const artifact = this._artifactFactory.build(solution, format, context.artifactPreferences())
      const enriched = this._decorator.apply(artifact, this._provenance.dump())

      const cmd: Command = {
        id: randomUUID(),
        query,
        solution,
        contextName: context.name,
        trace: this.state.trace,
        timestamp: Date.now(),
      }
      this.state.commit(cmd)
      this.state.reset()

      this._telemetry.event('turn.complete', {
        context: context.name,
        format,
        turn: this.state.turn,
      })

      this._lifecycle.recordLLMSuccess()
      return enriched
    })
  }

  protected async _solve(
    query: Query,
    context: IDomainContext,
    extras: Record<string, unknown>,
  ): Promise<Solution> {
    // Strategy: try a registered solver first
    const problemClass = context.resolveIntent(query)
    if (problemClass) {
      const solver = this._solverDispatcher.select(problemClass.solver, context)
      if (solver) {
        return solver.solve(query, context)
      }
    }

    // Fall back to LLM tool loop
    return this._llmToolLoop(query, context, extras)
  }

  private async _llmToolLoop(
    query: Query,
    context: IDomainContext,
    extras: Record<string, unknown>,
  ): Promise<Solution> {
    const config = this._config
    const maxRounds = config?.maxToolRounds ?? 5
    const tools = this._toolRegistry.all()
    const systemPrompt = context.systemPromptExtension()

    const messages: Message[] = [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: query.text },
    ]

    for (let round = 0; round < maxRounds; round++) {
      const request: CompletionRequest = {
        messages,
        tools: tools.length > 0
          ? tools.map(t => t.toVendorSpec(this._llmClient.vendor))
          : undefined,
      }

      let response
      try {
        response = await this._llmClient.complete(request)
        this._lifecycle.recordLLMSuccess()
      } catch (err) {
        this._lifecycle.recordLLMFailure()
        throw err
      }

      if (response.stopReason === 'tool_use' && response.toolCalls?.length) {
        messages.push({ role: 'assistant', content: response.content })
        for (const toolCall of response.toolCalls) {
          const result = await this._executeTool(toolCall)
          messages.push({ role: 'tool', content: JSON.stringify(result) })
        }
        continue
      }

      return {
        content: response.content,
        format: query.format ?? 'text',
        sources: this._provenance.dump().map(p => ({ tag: p.tag, ref: p.source })),
        metadata: { extras },
      }
    }

    return {
      content: `[TokenBudgetExceeded] Truncated after ${maxRounds} tool rounds.`,
      format: 'text',
      sources: [],
    }
  }

  private async _executeTool(toolCall: ToolCall): Promise<unknown> {
    const tool = this._toolRegistry.get(toolCall.name)
    if (!tool) {
      return { error: `Tool not found: ${toolCall.name}` }
    }
    try {
      return await tool.execute(toolCall.args)
    } catch (err) {
      console.error(`[OOAgent] Tool execution error: ${toolCall.name}`, err)
      return { error: (err as Error).message }
    }
  }

  private _handleFailure(
    err: unknown,
    context: IDomainContext,
    _snapshotId: string,
  ): Artifact {
    this.state.transition('FAILURE')
    let artifact: Artifact
    if (err instanceof ScopeExitError) {
      artifact = this._artifactFactory.buildScopeExit(context.name, err.query)
    } else if (err instanceof ConstraintViolationError) {
      artifact = this._artifactFactory.buildError(err.message, context.name)
    } else {
      artifact = this._artifactFactory.buildError((err as Error).message, context.name)
    }
    this.state.transition('DELIVERING')
    this.state.reset()
    this._lifecycle.recordLLMFailure()
    return artifact
  }
}

// Null Object for telemetry — used when no provider is injected
const NULL_TELEMETRY: ITelemetryProvider = {
  async span<T>(_name: string, fn: () => Promise<T>): Promise<T> { return fn() },
  counter: () => undefined,
  gauge: () => undefined,
  histogram: () => undefined,
  event: () => undefined,
}
