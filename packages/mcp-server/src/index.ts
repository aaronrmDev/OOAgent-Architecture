// @ooagent/mcp-server — OOAgent MCP Server
// Exposes OOAgent's ITool registry as an MCP (Model Context Protocol) server.
// Claude connects to this server and discovers tools registered in OOAgent's ToolRegistry.
//
// Protocol: MCP 1.0 (JSON-RPC 2.0 over stdio or SSE)
// Reference: https://modelcontextprotocol.io/

export { OOAgentMCPServer } from './server.js'
export { OOAgentMCPPlugin } from './plugin.js'
export type { MCPServerConfig } from './server.js'
