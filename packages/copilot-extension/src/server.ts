// @ooagent/copilot-extension/server.ts
// CopilotExtensionServer: HTTP server that implements the Copilot Extensions
// agent protocol. Receives SSE streams from GitHub, pipes them to OOAgent,
// and streams the response back to Copilot Chat.

import { createServer, IncomingMessage, ServerResponse } from 'node:http'
import { CopilotPayloadVerifier } from './verifier.js'

// Copilot Extensions message types (subset of GitHub's agent protocol)
interface CopilotMessage {
  role:    'user' | 'assistant' | 'system' | 'copilot'
  content: string
}

interface CopilotRequest {
  messages: CopilotMessage[]
  copilot_thread_id?: string
}

// Minimal OOAgent interface (no hard dependency on ooagent core)
interface IOOAgentRuntime {
  respond(query: { text: string; metadata?: Record<string, unknown> }): Promise<{ content: string; format: string }>
  readonly isReady: boolean
}

export interface CopilotExtensionConfig {
  /** Port to listen on. Default: 3000 */
  port?: number
  /** GitHub Webhook Secret for payload verification */
  webhookSecret?: string
  /** System prompt prepended to every Copilot request */
  systemPrompt?: string
}

export class CopilotExtensionServer {
  private readonly _agent: IOOAgentRuntime
  private readonly _config: Required<CopilotExtensionConfig>
  private readonly _verifier: CopilotPayloadVerifier | null

  constructor(agent: IOOAgentRuntime, config: CopilotExtensionConfig = {}) {
    this._agent  = agent
    this._config = {
      port:         config.port         ?? 3000,
      webhookSecret: config.webhookSecret ?? '',
      systemPrompt:  config.systemPrompt  ?? 'You are OOAgent, an object-oriented AI agent. Respond concisely and accurately.',
    }
    this._verifier = this._config.webhookSecret
      ? new CopilotPayloadVerifier(this._config.webhookSecret)
      : null
  }

  start(): void {
    const server = createServer(this._handleRequest.bind(this))
    server.listen(this._config.port, () => {
      console.error(`[CopilotExtension] Server listening on port ${this._config.port}`)
    })
  }

  private async _handleRequest(req: IncomingMessage, res: ServerResponse): Promise<void> {
    if (req.method === 'GET' && req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ status: 'ok', agent: this._agent.isReady }))
      return
    }

    if (req.method !== 'POST' || req.url !== '/') {
      res.writeHead(404)
      res.end()
      return
    }

    // Read and verify body
    const rawBody = await this._readBody(req)
    if (this._verifier) {
      try {
        this._verifier.verify(req.headers['x-github-token'] as string, rawBody)
      } catch (err) {
        res.writeHead(401, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ error: (err as Error).message }))
        return
      }
    }

    let body: CopilotRequest
    try {
      body = JSON.parse(rawBody.toString('utf8')) as CopilotRequest
    } catch {
      res.writeHead(400)
      res.end('Bad JSON')
      return
    }

    // Extract the latest user message
    const userMessages = body.messages.filter(m => m.role === 'user')
    const lastUser = userMessages.at(-1)
    if (!lastUser) {
      res.writeHead(422)
      res.end('No user message')
      return
    }

    // Stream response via SSE (Copilot Extensions protocol)
    res.writeHead(200, {
      'Content-Type':  'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection':    'keep-alive',
      'X-Accel-Buffering': 'no',
    })

    try {
      const artifact = await this._agent.respond({
        text: lastUser.content,
        metadata: { copilotThreadId: body.copilot_thread_id },
      })

      // Copilot Extensions SSE format: data: {"choices":[{"delta":{"content":"..."}}]}
      const chunks = this._chunkText(artifact.content, 40)
      for (const chunk of chunks) {
        const event = JSON.stringify({
          choices: [{ delta: { content: chunk, role: 'assistant' }, index: 0 }],
        })
        res.write(`data: ${event}\n\n`)
      }

      // Signal end of stream
      res.write('data: [DONE]\n\n')
    } catch (err) {
      const errorEvent = JSON.stringify({
        choices: [{
          delta: { content: `\n\n**Error:** ${(err as Error).message}`, role: 'assistant' },
          index: 0,
        }],
      })
      res.write(`data: ${errorEvent}\n\n`)
      res.write('data: [DONE]\n\n')
    }

    res.end()
  }

  private _readBody(req: IncomingMessage): Promise<Buffer> {
    return new Promise((resolve, reject) => {
      const chunks: Buffer[] = []
      req.on('data', (chunk: Buffer) => chunks.push(chunk))
      req.on('end', () => resolve(Buffer.concat(chunks)))
      req.on('error', reject)
    })
  }

  // Split text into chunks for streaming
  private _chunkText(text: string, size: number): string[] {
    const chunks: string[] = []
    for (let i = 0; i < text.length; i += size) {
      chunks.push(text.slice(i, i + size))
    }
    return chunks
  }
}
