// plugins/index.ts — barrel export for all plugin capabilities
export { AbstractPlugin }       from './base-plugin.js'
export { PluginRegistry }       from './registry.js'

export { LoggingPlugin }        from './logging/index.js'
export type { LoggingPluginOptions } from './logging/index.js'

export { RateLimitPlugin }      from './rate-limit/index.js'
export type { RateLimitOptions } from './rate-limit/index.js'

export { CachePlugin }          from './cache/index.js'
export type { CachePluginOptions } from './cache/index.js'

export { OpenTelemetryPlugin }  from './opentelemetry/index.js'
export type { OtelPluginOptions } from './opentelemetry/index.js'

export {
  ToolKitPlugin,
  DateTimeTool,
  CalculatorTool,
  HttpFetchTool,
}                               from './tool-kit/index.js'
export type { ToolKitPluginOptions }             from './tool-kit/index.js'
export type { HttpFetchToolOptions }             from './tool-kit/http-fetch-tool.js'

export { AuditPlugin }          from './audit/index.js'
export type { AuditPluginOptions, AuditEntry } from './audit/index.js'

export { ScopeGuardPlugin }     from './scope-guard/index.js'
export type { ScopeGuardOptions } from './scope-guard/index.js'

export {
  SecurityPlugin,
  DefaultSecurityPolicy,
  DEFAULT_SECURITY_POLICY,
  SecureToolWrapper,
}                               from './security/index.js'
export type {
  SecurityPluginOptions,
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
}                               from './security/index.js'
