// plugins/security/secure-tool-wrapper.ts
// SecureToolWrapper — wraps any ITool with the full security policy gate.
//
// Every call to execute() is intercepted:
//   1. Access control check  (Zero Trust, RBAC, SOC2)
//   2. Input validation      (LLM01, LLM04, LLM06, GDPR)
//   3. Delegated execution   (original tool)
//   4. Output validation     (LLM02, ASVS V5.3)
//   5. Audit record          (SOC2, HIPAA, PCI DSS)

import type { ISecurityPolicy } from './protocols.js'

interface ITool {
  readonly name: string
  readonly description: string
  inputSchema(): Record<string, unknown>
  execute(args: Record<string, unknown>): Promise<unknown>
  toVendorSpec(vendor: string): Record<string, unknown>
}

export class SecureToolWrapper implements ITool {
  private readonly _inner: ITool
  private readonly _policy: ISecurityPolicy
  private _agentId: string

  constructor(inner: ITool, policy: ISecurityPolicy, agentId = 'unknown') {
    this._inner   = inner
    this._policy  = policy
    this._agentId = agentId
  }

  get name():        string { return this._inner.name }
  get description(): string { return this._inner.description }

  inputSchema(): Record<string, unknown> { return this._inner.inputSchema() }
  toVendorSpec(v: string): Record<string, unknown> { return this._inner.toVendorSpec(v) }

  setAgentId(id: string): void { this._agentId = id }

  async execute(args: Record<string, unknown>): Promise<unknown> {
    const tool = this.name
    const agent = this._agentId

    // ① Zero Trust access check (NIST SP 800-207, OWASP API1/2, SOC2 CC6.1)
    const access = this._policy.checkAccess(agent, tool)
    if (!access.allowed) {
      return this._denied('Access denied', access.reason ?? 'Policy violation', tool)
    }

    // ② Input validation (LLM01, LLM04, LLM06, GDPR Art.25)
    const inputCheck = this._policy.validateInput(args, tool)
    if (!inputCheck.allowed) {
      return this._denied('Input validation failed', inputCheck.reason ?? 'Policy violation', tool)
    }

    // ③ Execute original tool
    let result: unknown
    const startMs = Date.now()
    try {
      result = await this._inner.execute(args)
    } catch (err) {
      this._policy.record({
        severity:    'medium',
        risk:        'LLM07_INSECURE_PLUGIN',
        framework:   'ISO_27001',
        message:     `Tool '${tool}' threw: ${(err as Error).message}`,
        agentId:     agent,
        toolName:    tool,
        remediation: 'Ensure tool.execute() throws ToolExecutionError with descriptive message',
      })
      throw err
    }

    // ④ Output validation (LLM02, OWASP ASVS V5.3)
    const outputCheck = this._policy.validateOutput(result, tool)
    if (!outputCheck.allowed) {
      return this._denied('Output validation failed', outputCheck.reason ?? 'Policy violation', tool)
    }

    // ⑤ Audit record (SOC2 CC6.2, HIPAA 164.312(b), PCI DSS 10.2)
    this._policy.record({
      severity:    'info',
      risk:        'N/A',
      framework:   'SOC2_TYPE2',
      message:     `Tool '${tool}' executed successfully in ${Date.now() - startMs}ms`,
      agentId:     agent,
      toolName:    tool,
      remediation: 'No action required',
    })

    return result
  }

  private _denied(type: string, reason: string, toolName: string): Record<string, string> {
    return { error: type, reason, tool: toolName, status: 'blocked_by_security_policy' }
  }
}
