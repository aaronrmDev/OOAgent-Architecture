// @ooagent/autogen-tools/plugin.ts
// AutoGenOOAgentPlugin: IPlugin that starts an AutoGen HTTP bridge
// alongside OOAgent so Python AutoGen agents can call OOAgent tools.

import { createServer } from 'node:http'
import { AutoGenToolBridge, AutoGenToolsConfig } from './adapter.js'

interface IAgentRuntime { agentId: string }
interface IToolRegistryRuntime {
  all(): Array<{ name: string; description: string; inputSchema(): Record<string, unknown>; execute(args: Record<string, unknown>): Promise<unknown> }>
}

export interface AutoGenPluginOptions extends AutoGenToolsConfig {
  /** Port for the HTTP bridge. Default: 8080 */
  port?: number
}

export class AutoGenOOAgentPlugin {
  readonly pluginId = 'ooagent.autogen-bridge'
  readonly version  = '2026.06.01'

  private readonly _registry: IToolRegistryRuntime
  private readonly _opts: AutoGenPluginOptions
  private _started = false

  constructor(toolRegistry: IToolRegistryRuntime, opts: AutoGenPluginOptions = {}) {
    this._registry = toolRegistry
    this._opts = opts
  }

  onRegister(_agent: IAgentRuntime): void {
    if (this._started) return
    const port = this._opts.port ?? 8080
    const bridge = new AutoGenToolBridge(this._registry, this._opts)
    const server = createServer(bridge.httpHandler() as Parameters<typeof createServer>[0])
    server.listen(port, () => {
      console.error(`[AutoGenOOAgentPlugin] HTTP bridge listening on port ${port}`)
      console.error(`[AutoGenOOAgentPlugin] Python AutoGen: GET http://localhost:${port}/tools`)
    })
    this._started = true
  }

  onDispose(): void { this._started = false }

  contributes(): Record<string, unknown[]> { return {} }
}
