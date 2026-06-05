// @ooagent/autogen-tools/adapter.ts
// Adapts OOAgent ITool to AutoGen FunctionTool schema.
//
// AutoGen FunctionTool contract:
//   { name, description, parameters (JSON Schema), handler(args) → Promise<string> }

interface IToolRuntime {
  name: string
  description: string
  inputSchema(): Record<string, unknown>
  execute(args: Record<string, unknown>): Promise<unknown>
}

interface IToolRegistryRuntime {
  all(): IToolRuntime[]
}

// AutoGen FunctionTool shape (TypeScript AutoGen core)
export interface AutoGenFunctionTool {
  name:        string
  description: string
  parameters:  Record<string, unknown>
  handler(args: Record<string, unknown>): Promise<string>
}

// AutoGen Python REST bridge tool spec (for Python autogen-agentchat)
export interface AutoGenPythonToolSpec {
  type:     'function'
  function: {
    name:        string
    description: string
    parameters:  Record<string, unknown>
  }
}

export interface AutoGenToolsConfig {
  /** If true, tool execution errors are returned as strings instead of throwing. Default: true */
  catchErrors?: boolean
  /** Serialize result as pretty JSON (default) or compact JSON */
  prettyJson?: boolean
}

/**
 * Converts all tools in an OOAgent ToolRegistry to AutoGen FunctionTools.
 *
 * @example
 * const tools = toAutoGenTools(registry)
 * const agent = new AssistantAgent('assistant', { tools })
 */
export function toAutoGenTools(
  registry: IToolRegistryRuntime,
  config: AutoGenToolsConfig = {},
): AutoGenFunctionTool[] {
  return registry.all().map(tool => toAutoGenTool(tool, config))
}

/**
 * Converts a single OOAgent ITool to an AutoGen FunctionTool.
 */
export function toAutoGenTool(
  tool: IToolRuntime,
  config: AutoGenToolsConfig = {},
): AutoGenFunctionTool {
  const catchErrors = config.catchErrors ?? true
  const pretty      = config.prettyJson  ?? true

  return {
    name:        tool.name,
    description: tool.description,
    parameters:  tool.inputSchema(),

    async handler(args: Record<string, unknown>): Promise<string> {
      try {
        const result = await tool.execute(args)
        return JSON.stringify(result, null, pretty ? 2 : 0)
      } catch (err) {
        if (!catchErrors) throw err
        return JSON.stringify({
          error:   (err as Error).message,
          tool:    tool.name,
          success: false,
        })
      }
    },
  }
}

/**
 * AutoGenToolBridge: exposes OOAgent tools over an HTTP REST endpoint
 * for Python AutoGen agents to call via HTTP function calling.
 *
 * Endpoint: POST /tools/:name
 * Body: { args: Record<string, unknown> }
 * Response: { result: string } | { error: string }
 */
export class AutoGenToolBridge {
  private readonly _tools: Map<string, AutoGenFunctionTool>

  constructor(registry: IToolRegistryRuntime, config: AutoGenToolsConfig = {}) {
    this._tools = new Map(
      toAutoGenTools(registry, config).map(t => [t.name, t]),
    )
  }

  /** Returns the OpenAI-compatible tool spec array for Python AutoGen. */
  toolSpecs(): AutoGenPythonToolSpec[] {
    return Array.from(this._tools.values()).map(t => ({
      type: 'function',
      function: {
        name:        t.name,
        description: t.description,
        parameters:  t.parameters,
      },
    }))
  }

  /** Executes a tool call by name. Used by the HTTP bridge handler. */
  async call(name: string, args: Record<string, unknown>): Promise<string> {
    const tool = this._tools.get(name)
    if (!tool) {
      return JSON.stringify({ error: `Tool '${name}' not found`, success: false })
    }
    return tool.handler(args)
  }

  /**
   * Creates a minimal HTTP handler for Node.js http.createServer.
   * Mount this at any path to expose the bridge to Python AutoGen.
   *
   * @example
   * const bridge = new AutoGenToolBridge(registry)
   * const server = http.createServer(bridge.httpHandler())
   * server.listen(8080)
   */
  httpHandler() {
    return async (req: { method?: string; url?: string; on(e: string, h: (d: Buffer) => void): void },
                  res: { writeHead(code: number, headers?: Record<string, string>): void; end(body?: string): void }) => {
      const url = req.url ?? ''

      // GET /tools → list all tools
      if (req.method === 'GET' && url === '/tools') {
        res.writeHead(200, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ tools: this.toolSpecs() }, null, 2))
        return
      }

      // POST /tools/:name → call a tool
      if (req.method === 'POST' && url.startsWith('/tools/')) {
        const name = decodeURIComponent(url.slice('/tools/'.length))
        let body = ''
        req.on('data', (chunk: Buffer) => { body += chunk.toString() })
        req.on('end', async () => {
          try {
            const { args = {} } = JSON.parse(body || '{}') as { args: Record<string, unknown> }
            const result = await this.call(name, args)
            res.writeHead(200, { 'Content-Type': 'application/json' })
            res.end(JSON.stringify({ result }))
          } catch {
            res.writeHead(400, { 'Content-Type': 'application/json' })
            res.end(JSON.stringify({ error: 'Bad Request' }))
          }
        })
        return
      }

      res.writeHead(404)
      res.end()
    }
  }
}
