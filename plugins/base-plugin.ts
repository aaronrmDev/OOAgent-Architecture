// plugins/base-plugin.ts — AbstractPlugin: reduces boilerplate for IPlugin implementors
import {
  IAgent,
  IPlugin,
  PluginContributions,
} from '../core/protocols.js'

export abstract class AbstractPlugin implements IPlugin {
  abstract readonly pluginId: string
  abstract readonly version: string

  // Called once by PluginRegistry.register() → OOAgent.initialize()
  // Override to perform setup (register event listeners, open connections, etc.)
  onRegister(_agent: IAgent<unknown, unknown>): void {}

  // Override to release resources allocated in onRegister.
  // Must be idempotent — may be called more than once.
  onDispose(): void {}

  // Override to declare what this plugin contributes to the agent.
  contributes(): PluginContributions {
    return {}
  }
}
