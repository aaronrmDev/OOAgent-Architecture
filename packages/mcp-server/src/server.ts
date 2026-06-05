// @ooagent/mcp-server/server.ts
// OOAgentMCPServer: wraps OOAgent's ToolRegistry and exposes it over the
// Model Context Protocol so Claude can call OOAgent tools natively.
//
// Claude connects to this MCP server via:
//   "mcpServers": {
//     "ooagent": {
//       "command": "node",
//       "args": ["node_modules/@ooagent/mcp-server/dist/bin/server.js"]
//     }
//   }

import { createServer, IncomingMessage, ServerResponse } from 'node:http'
import { randomUUID } from 'node:crypto'

// Minimal MCP protocol types (MCP 1.0 / JSON-RPC 2.0)
interface MCPRequest {
  jsonrpc: '2.0'
  id: string | number
  method: string
  params?: Record<string, unknown>
}

interface MCPResponse {
  jsonrpc: '2.0'
  id: string | number
  result?: unknown
  error?: { code: number; message: string; data?: unknown }
}

interface MCPTool {
  name: string
  description: string
  inputSchema: Record<string, unknown>
}

// Minimal ITool interface (matches core/protocols.ts without importing it
// to keep this package free of hard OOAgent dependency at runtime)
interface IToolRuntime {
  name: string
  description: string
  inputSchema(): Record<string, unknown>
  execute(args: Record<string, unknown>): Promise<unknown>
}

interface IToolRegistryRuntime {
  all(): IToolRuntime[]
  get(name: string): IToolRuntime | undefined
}

export interface MCPServerConfig {
  /** Port for SSE transport. Default: 3333 */
  port?: number
  /** Transport: 'stdio' (default) or 'sse' */
  transport?: 'stdio' | 'sse'
  /** Server name reported in MCP initialize response */
  serverName?: string
  /** Server version reported in MCP initialize response */
  serverVersion?: string
}

export class OOAgentMCPServer {
  private readonly _registry: IToolRegistryRuntime
  private readonly _config: Required<MCPServerConfig>

  constructor(toolRegistry: IToolRegistryRuntime, config: MCPServerConfig = {}) {
    this._registry = toolRegistry
    this._config = {
      port:          config.port          ?? 3333,
      transport:     config.transport     ?? 'stdio',
      serverName:    config.serverName    ?? 'ooagent-mcp',
      serverVersion: config.serverVersion ?? '2026.06.01',
    }
  }

  /** Start the MCP server on the configured transport. */
  async start(): Promise<void> {
    if (this._config.transport === 'stdio') {
      await this._serveStdio()
    } else {
      await this._serveSSE()
    }
  }

  // ── Stdio transport (default — works with Claude desktop app) ─────────────
  private async _serveStdio(): Promise<void> {
    process.stdin.setEncoding('utf8')
    let buffer = ''

    process.stdin.on('data', async (chunk: string) => {
      buffer += chunk
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue
        try {
          const request: MCPRequest = JSON.parse(trimmed)
          const response = await this._handle(request)
          process.stdout.write(JSON.stringify(response) + '\n')
        } catch {
          // Ignore malformed JSON
        }
      }
    })
  }

  // ── SSE transport (works with Claude.ai web + remote MCP) ─────────────────
  private async _serveSSE(): Promise<void> {
    const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
      if (req.method === 'GET' && req.url === '/sse') {
        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'Access-Control-Allow-Origin': '*',
        })
        // SSE handshake
        res.write(`data: ${JSON.stringify({ type: 'endpoint', endpoint: '/message' })}\n\n`)
        req.socket.on('close', () => res.end())
      } else if (req.method === 'POST' && req.url === '/message') {
        let body = ''
        req.on('data', (chunk: Buffer) => { body += chunk.toString() })
        req.on('end', async () => {
          try {
            const request: MCPRequest = JSON.parse(body)
            const response = await this._handle(request)
            res.writeHead(200, { 'Content-Type': 'application/json' })
            res.end(JSON.stringify(response))
          } catch {
            res.writeHead(400)
            res.end('Bad Request')
          }
        })
      } else {
        res.writeHead(404)
        res.end()
      }
    })

    server.listen(this._config.port, () => {
      console.error(`[OOAgent MCP] SSE server listening on port ${this._config.port}`)
    })
  }

  // ── MCP method dispatcher ─────────────────────────────────────────────────
  private async _handle(req: MCPRequest): Promise<MCPResponse> {
    const ok = (result: unknown): MCPResponse => ({
      jsonrpc: '2.0', id: req.id, result,
    })
    const err = (code: number, message: string): MCPResponse => ({
      jsonrpc: '2.0', id: req.id, error: { code, message },
    })

    switch (req.method) {
      case 'initialize':
        return ok({
          protocolVersion: '2024-11-05',
          capabilities: { tools: { listChanged: false } },
          serverInfo: {
            name:    this._config.serverName,
            version: this._config.serverVersion,
          },
        })

      case 'tools/list':
        return ok({ tools: this._listTools() })

      case 'tools/call': {
        const { name, arguments: args = {} } = (req.params ?? {}) as {
          name: string
          arguments: Record<string, unknown>
        }
        return ok(await this._callTool(name, args))
      }

      case 'ping':
        return ok({})

      default:
        return err(-32601, `Method not found: ${req.method}`)
    }
  }

  private _listTools(): MCPTool[] {
    return this._registry.all().map(tool => ({
      name:        tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema(),
    }))
  }

  private async _callTool(name: string, args: Record<string, unknown>): Promise<unknown> {
    const tool = this._registry.get(name)
    if (!tool) {
      return { error: `Tool '${name}' not found in OOAgent ToolRegistry` }
    }
    try {
      const result = await tool.execute(args)
      return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] }
    } catch (err) {
      return {
        content: [{ type: 'text', text: `Error: ${(err as Error).message}` }],
        isError: true,
      }
    }
  }
}
