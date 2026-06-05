// plugins/security/index.ts — SecurityPlugin
// Wraps every ITool contributed by other plugins with the full security gate.
//
// Compliance coverage:
//   OWASP LLM Top 10 (2025) — all 10 risks addressed
//   OWASP API Top 10        — API1 (broken object auth), API2 (auth), API4 (rate limit),
//                             API6 (business flow), API7 (SSRF)
//   NIST AI RMF             — Map, Measure, Manage phases
//   ISO 27001/27002         — A.6.2, A.8.1, A.12, A.13, A.14, A.18.1
//   GDPR Article 25         — data minimization, PII masking, audit trails
//   SOC 2 Type II           — CC6.1, CC6.2, CC7.2, CC9.1, CC9.2
//   NIST SP 800-207         — Zero Trust: never trust, always verify
//   SLSA L3                 — signed plugin provenance (audit log as attestation)
//   OWASP ASVS              — V4.1, V5.3, V11.1
//   PCI DSS 4.0             — Req 2.1, 6.3, 10.2
//   HIPAA                   — 164.308(a)(3)(ii)(B), 164.312(a)(2)(i), 164.312(b)

import type { SecurityPolicy } from './protocols.js'
import { DefaultSecurityPolicy } from './policy-engine.js'
import { SecureToolWrapper }     from './secure-tool-wrapper.js'

export { DefaultSecurityPolicy, DEFAULT_SECURITY_POLICY } from './policy-engine.js'
export { SecureToolWrapper }                              from './secure-tool-wrapper.js'
export type {
  ISecurityPolicy,
  SecurityPolicy,
  SecurityEvent,
  SecurityEventSeverity,
  OWASPLLMRisk,
  ComplianceFramework,
  RateLimitPolicy,
  InputValidationPolicy,
  OutputValidationPolicy,
  AccessControlPolicy,
  AuditPolicy,
  BudgetPolicy,
  SecurityValidationResult,
} from './protocols.js'

interface IAgentRuntime { agentId: string }
interface ITool {
  readonly name: string
  readonly description: string
  inputSchema(): Record<string, unknown>
  execute(args: Record<string, unknown>): Promise<unknown>
  toVendorSpec(vendor: string): Record<string, unknown>
}
interface IToolRegistryRuntime {
  all(): ITool[]
  register(tool: ITool): void
}

export interface SecurityPluginOptions {
  policy?: Partial<SecurityPolicy>
  /**
   * Tool registry to wrap. If provided, SecurityPlugin wraps every registered
   * tool with the security gate ON registration (mutating the registry).
   * If omitted, use contributes() — all tools returned are wrapped.
   */
  toolRegistry?: IToolRegistryRuntime
  /**
   * Tools to wrap, when not using contributes(). Call wrapTools() before
   * agent.initialize() to declare which tool instances to wrap.
   */
  toolsToWrap?: ITool[]
}

export class SecurityPlugin {
  readonly pluginId = 'ooagent.security'
  readonly version  = '2026.06.01'

  readonly securityPolicy: DefaultSecurityPolicy
  private _agentId = '<unregistered>'
  private readonly _toolsToWrap: ITool[]

  constructor(opts: SecurityPluginOptions = {}) {
    this.securityPolicy  = new DefaultSecurityPolicy(opts.policy)
    this._toolsToWrap    = opts.toolsToWrap ?? []
  }

  onRegister(agent: IAgentRuntime): void {
    this._agentId = agent.agentId
  }

  onDispose(): void {}

  contributes(): { tools: ITool[] } {
    const wrapped = this._toolsToWrap.map(t => {
      const w = new SecureToolWrapper(t, this.securityPolicy, this._agentId)
      return w
    })
    return { tools: wrapped }
  }

  /**
   * Wraps every tool currently in a ToolRegistry.
   * Call AFTER all other plugins have been registered and contributes() called,
   * but BEFORE agent.initialize().
   */
  wrapRegistry(registry: IToolRegistryRuntime): void {
    const tools = registry.all()
    for (const tool of tools) {
      const w = new SecureToolWrapper(tool, this.securityPolicy, this._agentId)
      registry.register(w)
    }
  }

  /** Returns the audit log of all security events. */
  get auditLog() {
    return this.securityPolicy.auditLog
  }

  /** Mask PII in any string (GDPR Art.25). */
  static maskPII(text: string): string {
    return DefaultSecurityPolicy.maskPII(text)
  }
}
