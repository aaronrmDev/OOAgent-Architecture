// @ooagent/autogen-tools — OOAgent → Microsoft AutoGen adapter
// Wraps each OOAgent ITool as an AutoGen FunctionTool so AutoGen agents
// can invoke them natively.
//
// AutoGen reference: https://microsoft.github.io/autogen/
// Compatible with: autogen-agentchat ^0.4 (Python) via REST bridge,
//                  and @microsoft/autogen-core (TypeScript preview)
//
// Usage (TypeScript AutoGen):
//   import { toAutoGenTools } from '@ooagent/autogen-tools'
//   import { ToolKitPlugin } from 'ooagent/plugins'
//   import { ToolRegistry } from 'ooagent/core'
//
//   const registry = new ToolRegistry()
//   new ToolKitPlugin().contributes().tools?.forEach(t => registry.register(t))
//   const autoGenTools = toAutoGenTools(registry)

export { toAutoGenTools, AutoGenToolBridge } from './adapter.js'
export { AutoGenOOAgentPlugin }              from './plugin.js'
export type { AutoGenFunctionTool, AutoGenToolsConfig } from './adapter.js'
