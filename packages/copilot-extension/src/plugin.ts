// @ooagent/copilot-extension/plugin.ts
// CopilotExtensionPlugin: IPlugin that starts the Copilot Extension server
// when OOAgent is initialized.

import { CopilotExtensionServer, CopilotExtensionConfig } from './server.js'

interface IAgentRuntime {
  agentId: string
  respond(q: { text: string; metadata?: Record<string, unknown> }): Promise<{ content: string; format: string }>
  readonly isReady: boolean
}

export class CopilotExtensionPlugin {
  readonly pluginId = 'ooagent.copilot-extension'
  readonly version  = '2026.06.01'

  private readonly _config: CopilotExtensionConfig
  private _started = false

  constructor(config: CopilotExtensionConfig = {}) {
    this._config = config
  }

  onRegister(agent: IAgentRuntime): void {
    if (this._started) return
    const server = new CopilotExtensionServer(agent, this._config)
    server.start()
    this._started = true
  }

  onDispose(): void { this._started = false }

  contributes(): Record<string, unknown[]> { return {} }
}
