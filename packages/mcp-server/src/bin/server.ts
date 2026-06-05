#!/usr/bin/env node
// @ooagent/mcp-server/bin/server.ts
// Standalone MCP stdio server entry point.
//
// Add to claude_desktop_config.json:
//   "mcpServers": {
//     "ooagent": {
//       "command": "node",
//       "args": ["<path>/node_modules/@ooagent/mcp-server/dist/bin/server.js"]
//     }
//   }
//
// Or for SSE (claude.ai web):
//   MCP_TRANSPORT=sse MCP_PORT=3333 node dist/bin/server.js

import { OOAgentMCPServer } from '../server.js'
import { ToolRegistry } from 'ooagent/core'
import { ToolKitPlugin } from 'ooagent/plugins'

// Bootstrap: register default tool kit
const toolRegistry = new ToolRegistry()
const toolKit = new ToolKitPlugin()
for (const tool of toolKit.contributes().tools ?? []) {
  toolRegistry.register(tool as Parameters<typeof toolRegistry.register>[0])
}

const transport = (process.env['MCP_TRANSPORT'] as 'stdio' | 'sse') ?? 'stdio'
const port      = parseInt(process.env['MCP_PORT'] ?? '3333', 10)

const server = new OOAgentMCPServer(toolRegistry, { transport, port })
server.start().catch(err => {
  console.error('[OOAgent MCP] Fatal error:', err)
  process.exit(1)
})
