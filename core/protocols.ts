// core/protocols.ts — all interface + type definitions (zero runtime dependencies)

// ── Primitive enumerations ───────────────────────────────────────────────────

export type SourceTag = 'measured' | 'assumed' | 'cited' | 'derived'

export type LLMVendor = 'anthropic' | 'openai' | 'gemini' | 'ollama'

export type AgentFSMState =
  | 'IDLE'
  | 'GATHERING'
  | 'AWAITING'
  | 'MODELING'
  | 'SOLVING'
  | 'VALIDATING'
  | 'DELIVERING'
  | 'FAILURE'
  | 'DEGRADED'

export type ArtifactFormat =
  | 'py' | 'ts' | 'md' | 'json' | 'sql' | 'html' | 'yaml' | 'mermaid' | 'text'

// ── Vocabulary & domain value objects ────────────────────────────────────────

export interface Term {
  readonly label: string
  readonly definition: string
  readonly canonical: boolean
}

export interface ProblemClass {
  readonly name: string
  readonly description: string
  readonly solver: string
}

export interface Invariant {
  readonly name: string
  readonly condition: string
  readonly severity: 'error' | 'warning'
  readonly rationale: string
}

export interface AntiPattern {
  readonly name: string
  readonly pattern: string
  readonly reason: string
}

export interface InputSpec {
  readonly name: string
  readonly type: string
  readonly required: boolean
  readonly description: string
}

export interface ArtifactPolicy {
  readonly preferredFormats: ArtifactFormat[]
  readonly typeHintsRequired: boolean
  readonly commentPolicy: 'none' | 'non-obvious' | 'all'
  readonly maxProseWords?: number
}

// ── Pipeline ──────────────────────────────────────────────────────────────────

export interface PipelineStepResult {
  readonly passed: boolean
  readonly extras: Record<string, unknown>
  readonly violation?: string
}

export interface PipelineStep {
  readonly name: string
  run(query: Query, context: IDomainContext): Promise<PipelineStepResult>
}

// ── LLM wire types ────────────────────────────────────────────────────────────

export type JSONSchema = Record<string, unknown>
export type VendorToolSpec = Record<string, unknown>

export interface Message {
  readonly role: 'system' | 'user' | 'assistant' | 'tool'
  readonly content: string
}

export interface TokenUsage {
  readonly inputTokens: number
  readonly outputTokens: number
}

export interface ToolCall {
  readonly id: string
  readonly name: string
  readonly args: Record<string, unknown>
}

export interface CompletionRequest {
  readonly messages: Message[]
  readonly maxTokens?: number
  readonly temperature?: number
  readonly tools?: VendorToolSpec[]
  readonly stopSequences?: string[]
}

export interface CompletionResponse {
  readonly content: string
  readonly stopReason: 'end_turn' | 'max_tokens' | 'tool_use' | 'stop_sequence'
  readonly usage: TokenUsage
  readonly toolCalls?: ToolCall[]
}

export interface CompletionChunk {
  readonly delta: string
  readonly done: boolean
}

// ── Domain query / solution / artifact types ──────────────────────────────────

export interface Query {
  readonly text: string
  readonly format?: ArtifactFormat
  readonly metadata?: Record<string, unknown>
}

export interface SourceRecord {
  readonly tag: SourceTag
  readonly ref: string
}

export interface Solution {
  readonly content: string
  readonly format: ArtifactFormat
  readonly sources: SourceRecord[]
  readonly metadata?: Record<string, unknown>
}

export interface ProvenanceRecord {
  readonly source: string
  readonly tag: SourceTag
  readonly timestamp: number
}

export interface Artifact {
  readonly content: string
  readonly format: ArtifactFormat
  readonly provenance: ProvenanceRecord[]
  readonly metadata?: Record<string, unknown>
}

// ── Session state types ───────────────────────────────────────────────────────

export type FSMTrace = Array<{ state: AgentFSMState; timestamp: number }>
export type StateObserver = (state: AgentFSMState) => void
export type Unsubscribe = () => void

export interface Memento {
  readonly id: string
  readonly fsm: AgentFSMState
  readonly turn: number
  readonly contextName: string
  readonly scratch: Record<string, unknown>
  readonly timestamp: number
}

export interface Command {
  readonly id: string
  readonly query: Query
  readonly solution: Solution
  readonly contextName: string
  readonly trace: FSMTrace
  readonly timestamp: number
}

// ── Configuration ─────────────────────────────────────────────────────────────

export interface IAgentConfig {
  readonly agentId?: string
  readonly maxRetries: number
  readonly maxToolRounds: number
  readonly turnTimeoutMs: number
  readonly toolTimeoutMs: number
  readonly specialistTimeoutMs: number
  readonly orchestrationTimeoutMs: number
  readonly contextResolutionThreshold: number
  readonly maxMementoEntries: number
  readonly circuitBreakerThreshold: number
  readonly logLevel?: 'debug' | 'info' | 'warn' | 'error'
}

export const DEFAULT_AGENT_CONFIG: IAgentConfig = {
  maxRetries: 3,
  maxToolRounds: 5,
  turnTimeoutMs: 60_000,
  toolTimeoutMs: 30_000,
  specialistTimeoutMs: 30_000,
  orchestrationTimeoutMs: 120_000,
  contextResolutionThreshold: 0.1,
  maxMementoEntries: 100,
  circuitBreakerThreshold: 5,
  logLevel: 'info',
}

// ── Plugin contributions ───────────────────────────────────────────────────────

export type ResponseDecoratorFn = (artifact: Artifact, provenance: ProvenanceRecord[]) => Artifact

export interface PluginContributions {
  readonly tools?: ITool[]
  readonly contexts?: IDomainContext[]
  readonly solvers?: ISolver[]
  readonly decorators?: ResponseDecoratorFn[]
}

// ── Health ────────────────────────────────────────────────────────────────────

export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy'

// ── Artifact tree (Composite pattern) ─────────────────────────────────────────

export interface IVisitor<T> {
  visit(node: IArtifactNode): T
}

export interface IArtifactNode {
  accept<T>(visitor: IVisitor<T>): T
  children(): IArtifactNode[]
}

export interface IPrototypable<T> {
  clone(): T
}

// ── Error types ───────────────────────────────────────────────────────────────

export class ConstraintViolationError extends Error {
  constructor(
    public readonly invariantName: string,
    public readonly offendingValue: unknown,
    public readonly inputs: Record<string, unknown>,
  ) {
    super(`Invariant violated: ${invariantName}`)
    this.name = 'ConstraintViolationError'
  }
}

export class FSMViolationError extends Error {
  constructor(
    public readonly from: AgentFSMState,
    public readonly to: AgentFSMState,
    public readonly trace: FSMTrace,
  ) {
    super(`Illegal FSM transition: ${from} → ${to}`)
    this.name = 'FSMViolationError'
  }
}

export class LifecycleError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'LifecycleError'
  }
}

export class ToolExecutionError extends Error {
  constructor(
    public readonly toolName: string,
    public readonly args: Record<string, unknown>,
    cause: unknown,
  ) {
    super(`Tool execution failed: ${toolName} — ${(cause as Error)?.message ?? cause}`)
    this.name = 'ToolExecutionError'
  }
}

export class TokenLimitError extends Error {
  constructor(
    public readonly requested: number,
    public readonly limit: number,
  ) {
    super(`Token limit exceeded: requested ${requested}, limit ${limit}`)
    this.name = 'TokenLimitError'
  }
}

export class ScopeExitError extends Error {
  constructor(
    public readonly context: string,
    public readonly query: string,
  ) {
    super(`Query out of scope for context: ${context}`)
    this.name = 'ScopeExitError'
  }
}

// ── Core interfaces ───────────────────────────────────────────────────────────

export interface IAgent<TQuery, TResponse> {
  respond(query: TQuery): Promise<TResponse>
  readonly agentId: string
  readonly state: ISessionState
}

export interface ILLMClient {
  complete(request: CompletionRequest): Promise<CompletionResponse>
  stream(request: CompletionRequest): AsyncIterableIterator<CompletionChunk>
  readonly modelId: string
  readonly vendor: LLMVendor
  readonly maxTokens: number
  readonly supportsTools: boolean
}

export interface IDomainContext {
  readonly name: string
  readonly version: string
  vocabulary(): Set<Term>
  problemClasses(): Set<ProblemClass>
  solvers(): Map<string, ISolver>
  invariants(): Invariant[]
  pipeline(): PipelineStep[]
  antiPatterns(): AntiPattern[]
  requiredInputs(pc: ProblemClass): InputSpec[]
  artifactPreferences(): ArtifactPolicy
  systemPromptExtension(): string
  resolveIntent(query: Query): ProblemClass | null
}

export interface ISolver {
  canSolve(problemClass: string): boolean
  solve(query: Query, ctx: IDomainContext): Promise<Solution>
}

export interface ITool {
  readonly name: string
  readonly description: string
  inputSchema(): JSONSchema
  execute(args: Record<string, unknown>): Promise<unknown>
  toVendorSpec(vendor: LLMVendor): VendorToolSpec
}

export interface IPlugin {
  readonly pluginId: string
  readonly version: string
  onRegister(agent: IAgent<unknown, unknown>): void
  onDispose(): void
  contributes(): PluginContributions
}

export interface ILifecycle {
  initialize(config: IAgentConfig): Promise<void>
  healthCheck(): Promise<HealthStatus>
  dispose(): Promise<void>
  readonly isReady: boolean
}

export interface ISessionState {
  readonly fsm: AgentFSMState
  readonly turn: number
  readonly contextName: string
  readonly trace: FSMTrace
  transition(to: AgentFSMState): void
  setContext(name: string): void
  snapshot(): Memento
  restore(id: string): void
  commit(cmd: Command): void
  subscribe(obs: StateObserver): Unsubscribe
  flush(): Promise<void>
  reset(): void
}

export interface ITelemetryProvider {
  span<T>(name: string, fn: () => Promise<T>): Promise<T>
  counter(name: string, delta?: number): void
  gauge(name: string, value: number): void
  histogram(name: string, value: number): void
  event(name: string, payload: Record<string, unknown>): void
}

export interface IArtifactFactory {
  build(solution: Solution, format: ArtifactFormat, policy: ArtifactPolicy): Artifact
  buildError(violation: string, ctx: string): Artifact
  buildMissingInputs(missing: InputSpec[], ctx: string): Artifact
  buildScopeExit(ctx: string, query: string): Artifact
}

export interface IOrchestrator {
  dispatch(query: Query, contexts: IDomainContext[]): Promise<Solution[]>
  synthesize(solutions: Solution[], original: Query): Promise<Solution>
}

// ── Composition interfaces ─────────────────────────────────────────────────────

export interface IContextHost<TContext> {
  readonly activeContext: TContext
}

export interface IConversationalObject {
  readonly history: Command[]
}

export interface IToolUser {
  readonly tools: ITool[]
}

export interface IObservable {
  subscribe(observer: StateObserver): Unsubscribe
}
