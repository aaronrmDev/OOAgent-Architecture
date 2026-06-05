// plugins/security/protocols.ts — Security contracts for OOAgent plugins
// Maps to: OWASP LLM Top 10 (2025), NIST AI RMF, ISO 27001/27002,
//          GDPR Art.25, SOC 2 Type II, NIST SP 800-207 Zero Trust,
//          SLSA L3, OWASP ASVS, PCI DSS 4.0, HIPAA.

// ── OWASP LLM Top 10 risk identifiers ────────────────────────────────────────

export type OWASPLLMRisk =
  | 'LLM01_PROMPT_INJECTION'          // input overrides system instructions
  | 'LLM02_INSECURE_OUTPUT'           // unvalidated output executed as code
  | 'LLM03_TRAINING_DATA_POISONING'   // compromised training data
  | 'LLM04_MODEL_DOS'                 // resource exhaustion via long inputs
  | 'LLM05_SUPPLY_CHAIN'             // compromised dependencies/plugins
  | 'LLM06_SENSITIVE_DISCLOSURE'      // model leaks PII from context
  | 'LLM07_INSECURE_PLUGIN'          // plugin executes without auth/validation
  | 'LLM08_EXCESSIVE_AGENCY'         // agent takes unintended high-impact actions
  | 'LLM09_OVERRELIANCE'             // system over-trusts model output without validation
  | 'LLM10_MODEL_THEFT'              // extraction via adversarial prompting

// ── Compliance frameworks ─────────────────────────────────────────────────────

export type ComplianceFramework =
  | 'OWASP_LLM_TOP10'
  | 'OWASP_API_TOP10'
  | 'NIST_AI_RMF'
  | 'ISO_27001'
  | 'GDPR_ART25'
  | 'SOC2_TYPE2'
  | 'NIST_SP800_207'   // Zero Trust
  | 'SLSA_L3'
  | 'OWASP_ASVS'
  | 'PCI_DSS_4'
  | 'HIPAA'

// ── Security events ───────────────────────────────────────────────────────────

export type SecurityEventSeverity = 'info' | 'low' | 'medium' | 'high' | 'critical'

export interface SecurityEvent {
  readonly id:          string
  readonly timestamp:   string            // ISO 8601 UTC
  readonly severity:    SecurityEventSeverity
  readonly risk:        OWASPLLMRisk | string
  readonly framework:   ComplianceFramework
  readonly message:     string
  readonly agentId:     string
  readonly toolName?:   string
  readonly input?:      string            // sanitized — no raw PII
  readonly remediation: string
}

// ── Policy types ──────────────────────────────────────────────────────────────

export interface RateLimitPolicy {
  readonly maxCallsPerMinute: number
  readonly maxCallsPerHour:   number
  readonly maxInputTokens:    number      // LLM04: Model DoS prevention
}

export interface InputValidationPolicy {
  readonly maxInputLength:     number     // LLM04: DoS prevention
  readonly blockedPatterns:    string[]   // LLM01: Prompt injection patterns
  readonly allowedHosts:       string[]   // SSRF prevention (OWASP API7)
  readonly piiMaskingEnabled:  boolean    // GDPR Art.25 / LLM06
}

export interface OutputValidationPolicy {
  readonly maxOutputLength:    number     // LLM02: Insecure output
  readonly htmlEscapeEnabled:  boolean    // OWASP ASVS V5.3
  readonly jsonParseStrict:    boolean    // LLM02: type enforcement
}

export interface AccessControlPolicy {
  readonly rbacEnabled:        boolean    // OWASP API1/2, SOC2 CC6.1
  readonly allowedAgentIds:    string[]   // Zero Trust: never trust, always verify
  readonly allowedTools:       string[]   // Least privilege (NIST SP 800-207)
  readonly requireMFA:         boolean    // SOC2 CC6.1
}

export interface AuditPolicy {
  readonly enabled:            boolean    // SOC2 CC6.2, HIPAA 164.312(b)
  readonly includeInput:       boolean    // note: PII must be masked first
  readonly includeOutput:      boolean
  readonly retentionDays:      number     // GDPR / PCI DSS compliance
  readonly sink?:              (event: SecurityEvent) => void | Promise<void>
}

export interface BudgetPolicy {
  readonly maxCostUsdPerHour:  number     // OWASP LLM09: unbounded consumption
  readonly maxToolCallsPerTurn: number    // LLM08: Excessive agency
  readonly alertThresholdPct:  number     // alert at X% of budget
}

export interface SecurityPolicy {
  readonly policyId:      string
  readonly version:       string
  readonly frameworks:    ComplianceFramework[]
  readonly rateLimit:     RateLimitPolicy
  readonly input:         InputValidationPolicy
  readonly output:        OutputValidationPolicy
  readonly access:        AccessControlPolicy
  readonly audit:         AuditPolicy
  readonly budget:        BudgetPolicy
}

// ── Interfaces ────────────────────────────────────────────────────────────────

/**
 * ISecurityPolicy — enforces compliance controls on every plugin tool call.
 * A single shared instance per agent (Singleton pattern, SOC2 CC9.1).
 */
export interface ISecurityPolicy {
  readonly policy: SecurityPolicy

  // Validates input before tool execution (LLM01, LLM04, GDPR Art.25)
  validateInput(input: Record<string, unknown>, toolName: string): SecurityValidationResult

  // Validates output before returning to agent (LLM02, OWASP ASVS V5.3)
  validateOutput(output: unknown, toolName: string): SecurityValidationResult

  // Checks access rights (OWASP API1/2, Zero Trust, SOC2 CC6.1)
  checkAccess(agentId: string, toolName: string): SecurityValidationResult

  // Records a security event (SOC2 CC6.2, HIPAA 164.312(b), PCI DSS 10.2)
  record(event: Omit<SecurityEvent, 'id' | 'timestamp'>): void
}

export interface SecurityValidationResult {
  readonly allowed: boolean
  readonly reason?: string
  readonly risk?:   OWASPLLMRisk | string
}
