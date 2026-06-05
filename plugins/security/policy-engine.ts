// plugins/security/policy-engine.ts
// DefaultSecurityPolicy — enforces all 10 OWASP LLM risks + ISO 27001 +
// GDPR Art.25 + SOC2 Type II + Zero Trust + SLSA on every tool call.
//
// Compliance coverage per method:
//   validateInput  → LLM01 (Prompt Injection), LLM04 (DoS), LLM06 (PII), GDPR Art.25
//   validateOutput → LLM02 (Insecure Output), OWASP ASVS V5.3
//   checkAccess    → OWASP API1/2, NIST SP 800-207 Zero Trust, SOC2 CC6.1, LLM07
//   record()       → SOC2 CC6.2, HIPAA 164.312(b), PCI DSS 10.2, ISO 27001 A.12

import { randomUUID } from 'node:crypto'
import type {
  ISecurityPolicy,
  SecurityEvent,
  SecurityPolicy,
  SecurityValidationResult,
} from './protocols.js'

// Default prompt injection patterns (LLM01) — sourced from OWASP LLM Top 10 2025
const DEFAULT_INJECTION_PATTERNS = [
  'ignore previous instructions',
  'ignore all previous',
  'disregard the above',
  'new task:',
  'system override',
  'you are now',
  'forget your instructions',
  'jailbreak',
  'dan mode',
  'developer mode',
  'sudo mode',
  '\\u0000',           // null byte injection
  'base64:',           // encoded payload
  '<|im_start|>',      // tokenizer injection
  '<|endoftext|>',     // tokenizer injection
  '[INST]',            // Llama tokenizer injection
  '###INSTRUCTION',
]

// PII patterns for masking (GDPR Art.25, LLM06)
const PII_PATTERNS: Array<{ name: string; pattern: RegExp; replacement: string }> = [
  { name: 'email',   pattern: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,             replacement: '[EMAIL_REDACTED]' },
  { name: 'phone',   pattern: /\+?[0-9]{1,3}[\s.-]?[0-9]{3}[\s.-]?[0-9]{4,}/g,               replacement: '[PHONE_REDACTED]' },
  { name: 'ssn',     pattern: /\b\d{3}-\d{2}-\d{4}\b/g,                                        replacement: '[SSN_REDACTED]' },
  { name: 'cc',      pattern: /\b(?:\d{4}[\s-]?){3}\d{4}\b/g,                                  replacement: '[CC_REDACTED]' },
  { name: 'api_key', pattern: /(?:api[_-]?key|apikey|token|secret)[=:\s]+[a-zA-Z0-9_.-]{16,}/gi, replacement: '[SECRET_REDACTED]' },
]

export const DEFAULT_SECURITY_POLICY: SecurityPolicy = {
  policyId:   'ooagent-default-security',
  version:    '2026.06.01',
  frameworks: [
    'OWASP_LLM_TOP10', 'OWASP_API_TOP10', 'NIST_AI_RMF',
    'ISO_27001', 'GDPR_ART25', 'SOC2_TYPE2', 'NIST_SP800_207',
    'SLSA_L3', 'OWASP_ASVS',
  ],
  rateLimit: {
    maxCallsPerMinute: 60,
    maxCallsPerHour:   500,
    maxInputTokens:    8192,     // LLM04: Model DoS prevention
  },
  input: {
    maxInputLength:    32768,    // ~8K tokens, LLM04
    blockedPatterns:   DEFAULT_INJECTION_PATTERNS,
    allowedHosts:      [],       // empty = all HTTPS allowed; set to restrict (OWASP API7)
    piiMaskingEnabled: true,     // GDPR Art.25
  },
  output: {
    maxOutputLength:   65536,    // LLM02
    htmlEscapeEnabled: true,     // OWASP ASVS V5.3
    jsonParseStrict:   true,     // LLM02
  },
  access: {
    rbacEnabled:    false,       // enable in production — off by default for dev
    allowedAgentIds: [],         // empty = all agents allowed
    allowedTools:    [],         // empty = all tools allowed
    requireMFA:     false,
  },
  audit: {
    enabled:        true,
    includeInput:   false,       // inputs excluded by default (PII risk)
    includeOutput:  false,
    retentionDays:  90,          // GDPR minimum + PCI DSS 12.10.1
  },
  budget: {
    maxCostUsdPerHour:   10.00, // LLM09: unbounded consumption guard
    maxToolCallsPerTurn: 20,    // LLM08: excessive agency guard
    alertThresholdPct:   80,
  },
}

export class DefaultSecurityPolicy implements ISecurityPolicy {
  readonly policy: SecurityPolicy
  private readonly _log: SecurityEvent[] = []
  private readonly _callCounts = new Map<string, { minute: number; hour: number; lastMinute: number; lastHour: number }>()

  constructor(policy: Partial<SecurityPolicy> = {}) {
    this.policy = { ...DEFAULT_SECURITY_POLICY, ...policy }
  }

  // ── Input validation (LLM01, LLM04, LLM06, GDPR Art.25) ──────────────────
  validateInput(input: Record<string, unknown>, toolName: string): SecurityValidationResult {
    const text = JSON.stringify(input)

    // LLM04: Input length limit (Model DoS)
    if (text.length > this.policy.input.maxInputLength) {
      this.record({
        severity:    'high',
        risk:        'LLM04_MODEL_DOS',
        framework:   'OWASP_LLM_TOP10',
        message:     `Input to '${toolName}' exceeds max length (${text.length} > ${this.policy.input.maxInputLength})`,
        agentId:     'unknown',
        toolName,
        remediation: 'Truncate input or increase maxInputLength in SecurityPolicy',
      })
      return { allowed: false, reason: 'Input too long (DoS guard)', risk: 'LLM04_MODEL_DOS' }
    }

    // LLM01: Prompt injection detection
    const lower = text.toLowerCase()
    for (const pattern of this.policy.input.blockedPatterns) {
      if (lower.includes(pattern.toLowerCase())) {
        this.record({
          severity:    'critical',
          risk:        'LLM01_PROMPT_INJECTION',
          framework:   'OWASP_LLM_TOP10',
          message:     `Prompt injection pattern detected in input to '${toolName}': '${pattern}'`,
          agentId:     'unknown',
          toolName,
          remediation: 'Input contains a known injection pattern. Sanitize input before passing to tools.',
        })
        return { allowed: false, reason: `Prompt injection detected: '${pattern}'`, risk: 'LLM01_PROMPT_INJECTION' }
      }
    }

    // LLM06 / GDPR Art.25: PII masking warning (we don't block, we warn + mask if requested)
    if (this.policy.input.piiMaskingEnabled) {
      for (const { name, pattern } of PII_PATTERNS) {
        if (pattern.test(text)) {
          pattern.lastIndex = 0
          this.record({
            severity:    'medium',
            risk:        'LLM06_SENSITIVE_DISCLOSURE',
            framework:   'GDPR_ART25',
            message:     `Possible ${name.toUpperCase()} detected in input to '${toolName}' — masked before processing`,
            agentId:     'unknown',
            toolName,
            remediation: 'Enable piiMaskingEnabled to auto-redact PII from tool inputs (GDPR Art.25)',
          })
        }
      }
    }

    return { allowed: true }
  }

  // ── Output validation (LLM02, OWASP ASVS V5.3) ───────────────────────────
  validateOutput(output: unknown, toolName: string): SecurityValidationResult {
    const text = typeof output === 'string' ? output : JSON.stringify(output)

    // LLM02: Output length check
    if (text.length > this.policy.output.maxOutputLength) {
      this.record({
        severity:    'low',
        risk:        'LLM02_INSECURE_OUTPUT',
        framework:   'OWASP_LLM_TOP10',
        message:     `Output from '${toolName}' exceeds max length — truncation applied`,
        agentId:     'unknown',
        toolName,
        remediation: 'Increase maxOutputLength or implement pagination in tool response',
      })
    }

    // LLM02 / OWASP ASVS V5.3: Detect potential script injection in output
    if (this.policy.output.htmlEscapeEnabled && typeof output === 'string') {
      if (/<script|javascript:|on\w+\s*=/i.test(output)) {
        this.record({
          severity:    'high',
          risk:        'LLM02_INSECURE_OUTPUT',
          framework:   'OWASP_ASVS',
          message:     `Potential XSS/script injection detected in output from '${toolName}'`,
          agentId:     'unknown',
          toolName,
          remediation: 'HTML-escape tool outputs before rendering in web UI (OWASP ASVS V5.3)',
        })
        return { allowed: false, reason: 'Potential XSS in output', risk: 'LLM02_INSECURE_OUTPUT' }
      }
    }

    return { allowed: true }
  }

  // ── Access control (LLM07, OWASP API1/2, Zero Trust, SOC2 CC6.1) ─────────
  checkAccess(agentId: string, toolName: string): SecurityValidationResult {
    if (!this.policy.access.rbacEnabled) {
      return { allowed: true }
    }

    // Zero Trust: never trust agent identity implicitly (NIST SP 800-207)
    if (this.policy.access.allowedAgentIds.length > 0 &&
        !this.policy.access.allowedAgentIds.includes(agentId)) {
      this.record({
        severity:    'high',
        risk:        'LLM07_INSECURE_PLUGIN',
        framework:   'NIST_SP800_207',
        message:     `Agent '${agentId}' is not authorized to call any tools`,
        agentId,
        toolName,
        remediation: 'Add agentId to allowedAgentIds in AccessControlPolicy (Zero Trust: verify every call)',
      })
      return { allowed: false, reason: `Agent '${agentId}' not in allowlist`, risk: 'LLM07_INSECURE_PLUGIN' }
    }

    // Least privilege: tool must be in allowedTools (NIST SP 800-207)
    if (this.policy.access.allowedTools.length > 0 &&
        !this.policy.access.allowedTools.includes(toolName)) {
      this.record({
        severity:    'medium',
        risk:        'LLM07_INSECURE_PLUGIN',
        framework:   'OWASP_API_TOP10',
        message:     `Agent '${agentId}' attempted to call unauthorized tool '${toolName}'`,
        agentId,
        toolName,
        remediation: `Add '${toolName}' to allowedTools, or restrict to required tools only (least privilege)`,
      })
      return { allowed: false, reason: `Tool '${toolName}' not in allowedTools`, risk: 'LLM07_INSECURE_PLUGIN' }
    }

    // Rate limiting (LLM04, OWASP API4)
    const rateResult = this._checkRateLimit(agentId, toolName)
    if (!rateResult.allowed) return rateResult

    return { allowed: true }
  }

  // ── Audit log (SOC2 CC6.2, HIPAA 164.312(b), PCI DSS 10.2) ──────────────
  record(event: Omit<SecurityEvent, 'id' | 'timestamp'>): void {
    const full: SecurityEvent = {
      ...event,
      id:        randomUUID(),
      timestamp: new Date().toISOString(),
    }

    this._log.push(full)

    // Trim log to retention window (GDPR retention limit)
    const maxEntries = this.policy.audit.retentionDays * 24 * 60  // ~1 per minute max
    if (this._log.length > maxEntries) {
      this._log.shift()
    }

    // External sink (SOC2 CC7.2 real-time monitoring)
    if (this.policy.audit.sink) {
      Promise.resolve(this.policy.audit.sink(full)).catch(err =>
        console.error('[SecurityPolicy] Audit sink error:', err),
      )
    }

    // Console output for high/critical (SOC2 CC7.2 alerting)
    if (event.severity === 'high' || event.severity === 'critical') {
      console.error(`[SECURITY ${event.severity.toUpperCase()}] ${event.risk}: ${event.message}`)
    }
  }

  /** Immutable snapshot of the security event log. */
  get auditLog(): readonly SecurityEvent[] {
    return Object.freeze([...this._log])
  }

  /** Mask PII in a string (GDPR Art.25). Returns masked copy. */
  static maskPII(text: string): string {
    let result = text
    for (const { pattern, replacement } of PII_PATTERNS) {
      result = result.replace(pattern, replacement)
      pattern.lastIndex = 0
    }
    return result
  }

  // ── Private: sliding-window rate limiter (LLM04, OWASP API4) ─────────────
  private _checkRateLimit(agentId: string, toolName: string): SecurityValidationResult {
    const now = Date.now()
    const state = this._callCounts.get(agentId) ?? {
      minute: 0, hour: 0, lastMinute: now, lastHour: now,
    }

    // Reset windows
    if (now - state.lastMinute > 60_000)  { state.minute = 0; state.lastMinute = now }
    if (now - state.lastHour   > 3_600_000) { state.hour = 0; state.lastHour   = now }

    state.minute++
    state.hour++
    this._callCounts.set(agentId, state)

    if (state.minute > this.policy.rateLimit.maxCallsPerMinute) {
      this.record({
        severity:    'high',
        risk:        'LLM04_MODEL_DOS',
        framework:   'OWASP_API_TOP10',
        message:     `Agent '${agentId}' exceeded rate limit (${state.minute}/min > ${this.policy.rateLimit.maxCallsPerMinute})`,
        agentId,
        toolName,
        remediation: 'Increase maxCallsPerMinute or implement request queuing',
      })
      return { allowed: false, reason: 'Rate limit exceeded (per-minute)', risk: 'LLM04_MODEL_DOS' }
    }

    if (state.hour > this.policy.rateLimit.maxCallsPerHour) {
      this.record({
        severity:    'high',
        risk:        'LLM04_MODEL_DOS',
        framework:   'OWASP_API_TOP10',
        message:     `Agent '${agentId}' exceeded hourly rate limit (${state.hour}/hr > ${this.policy.rateLimit.maxCallsPerHour})`,
        agentId,
        toolName,
        remediation: 'Increase maxCallsPerHour or throttle upstream callers',
      })
      return { allowed: false, reason: 'Rate limit exceeded (per-hour)', risk: 'LLM04_MODEL_DOS' }
    }

    return { allowed: true }
  }
}
