// @ooagent/mcp-server/plugin.ts
// OOAgentMCPPlugin: an IPlugin that starts the MCP server when the agent
// is initialized, exposing all registered tools to Claude.
//
// Usage:
//   const mcp = new OOAgentMCPPlugin({ transport: 'stdio' })
//   agent.pluginRegistry.register(mcp)
//   await agent.initialize(config)
//   // MCP server is now live; Claude can connect and call tools

import { OOAgentMCPServer, MCPServerConfig } from './server.js'

// Minimal IPlugin-compatible interface (no hard dependency on ooagent core)
interface IAgentRuntime {
  agentId: string
  // Access to toolRegistry injected via constructor
}

interface IToolRegistryRuntime {
  all(): Array<{ name: string; description: string; inputSchema(): Record<string, unknown>; execute(args: Record<string, unknown>): Promise<unknown> }>
  get(name: string): { name: string; description: string; inputSchema(): Record<string, unknown>; execute(args: Record<string, unknown>): Promise<unknown> } | undefined
}

export class OOAgentMCPPlugin {
  readonly pluginId = 'ooagent.mcp-server'
  readonly version  = '2026.06.01'

  private readonly _config: MCPServerConfig
  private readonly _toolRegistry: IToolRegistryRuntime
  private _server: OOAgentMCPServer | null = null
  private _started = false

  constructor(toolRegistry: IToolRegistryRuntime, config: MCPServerConfig = {}) {
    this._toolRegistry = toolRegistry
    this._config = config
  }

  onRegister(_agent: IAgentRuntime): void {
    if (this._started) return
    this._server = new OOAgentMCPServer(this._toolRegistry, this._config)
    this._server.start().catch(err => {
      console.error('[OOAgentMCPPlugin] Failed to start MCP server:', err)
    })
    this._started = true
    console.error(`[OOAgentMCPPlugin] MCP server started (transport: ${this._config.transport ?? 'stdio'})`)
  }

  onDispose(): void {
    // MCP server does not hold closeable resources in stdio mode.
    // In SSE mode, the http.Server closes with process exit.
    this._started = false
    this._server = null
  }

  contributes(): { tools?: unknown[]; contexts?: unknown[]; solvers?: unknown[]; decorators?: unknown[] } {
    return {}
  }
}
