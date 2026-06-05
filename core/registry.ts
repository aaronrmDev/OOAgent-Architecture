// core/registry.ts — ContextRegistry (Singleton), ToolRegistry, PluginRegistry
import {
  ArtifactFormat,
  IDomainContext,
  IPlugin,
  ITool,
  Query,
} from './protocols.js'

// Inline minimal NullContext — avoids circular dependency with contexts/
// The full NullContext class lives in contexts/null_context.ts
function createInlineNullContext(): IDomainContext {
  return {
    name: 'NullContext',
    version: '1.0',
    vocabulary: () => new Set(),
    problemClasses: () => new Set(),
    solvers: () => new Map(),
    invariants: () => [],
    pipeline: () => [],
    antiPatterns: () => [],
    requiredInputs: () => [],
    artifactPreferences: () => ({
      preferredFormats: ['text' as ArtifactFormat],
      typeHintsRequired: false,
      commentPolicy: 'none' as const,
    }),
    systemPromptExtension: () =>
      'NullContext v1.0 is active. Do not make domain-specific claims.',
    resolveIntent: () => null,
  }
}

// Singleton — single source of truth for active IDomainContext — §4 GoF
export class ContextRegistry {
  private static _instance: ContextRegistry | null = null
  private readonly _contexts = new Map<string, IDomainContext>()
  private _nullContextFactory: () => IDomainContext = createInlineNullContext
  private _threshold = 0.1

  private constructor() {}

  static getInstance(): ContextRegistry {
    if (!ContextRegistry._instance) {
      ContextRegistry._instance = new ContextRegistry()
    }
    return ContextRegistry._instance
  }

  // Test hook
  static reset(): void {
    ContextRegistry._instance = null
  }

  setNullContextFactory(factory: () => IDomainContext): void {
    this._nullContextFactory = factory
  }

  setThreshold(threshold: number): void {
    this._threshold = threshold
  }

  register(context: IDomainContext): void {
    const key = `${context.name}@${context.version}`
    this._contexts.set(key, context)
  }

  // Context resolution algorithm — §9 CLAUDE.md
  resolve(query: Query): IDomainContext {
    let bestScore = -1
    let bestContext: IDomainContext | null = null
    let tieVersion = ''

    for (const ctx of this._contexts.values()) {
      const score = this._score(query, ctx)
      if (score > bestScore) {
        bestScore = score
        bestContext = ctx
        tieVersion = ctx.version
      } else if (score === bestScore && score > 0 && ctx.version > tieVersion) {
        // Tie: pick highest version
        bestContext = ctx
        tieVersion = ctx.version
      }
    }

    if (!bestContext || bestScore < this._threshold) {
      return this._nullContextFactory()
    }
    return bestContext
  }

  get registeredNames(): string[] {
    return Array.from(this._contexts.values()).map(c => `${c.name} v${c.version}`)
  }

  private _score(query: Query, ctx: IDomainContext): number {
    const text = query.text.toLowerCase()
    let score = 0

    for (const term of ctx.vocabulary()) {
      if (text.includes(term.label.toLowerCase())) {
        score += term.canonical ? 2 : 1
      }
    }
    for (const pc of ctx.problemClasses()) {
      if (text.includes(pc.name.toLowerCase())) {
        score += 3
      }
    }
    if (ctx.resolveIntent(query) !== null) {
      score += 5
    }
    return score
  }
}

export class ToolRegistry {
  private readonly _tools = new Map<string, ITool>()

  register(tool: ITool): void {
    this._tools.set(tool.name, tool)
  }

  get(name: string): ITool | undefined {
    return this._tools.get(name)
  }

  all(): ITool[] {
    return Array.from(this._tools.values())
  }

  has(name: string): boolean {
    return this._tools.has(name)
  }
}

export class PluginRegistry {
  private readonly _plugins = new Map<string, IPlugin>()

  register(plugin: IPlugin): void {
    const key = `${plugin.pluginId}@${plugin.version}`
    if (this._plugins.has(key)) {
      throw new Error(`Duplicate plugin registration: ${key}`)
    }
    this._plugins.set(key, plugin)
  }

  verify(): void {
    // Health check hook — subclasses add specific checks
  }

  async disposeAll(): Promise<void> {
    for (const plugin of this._plugins.values()) {
      try {
        plugin.onDispose()
      } catch (err) {
        // Isolate plugin failures — never crash the agent — §16 CLAUDE.md
        console.error(`[PluginRegistry] Dispose failed for ${plugin.pluginId}:`, err)
      }
    }
  }

  all(): IPlugin[] {
    return Array.from(this._plugins.values())
  }
}
