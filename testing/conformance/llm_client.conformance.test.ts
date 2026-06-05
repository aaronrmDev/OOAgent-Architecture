// testing/conformance/llm_client.conformance.test.ts
// ILLMClient conformance suite — §17 CLAUDE.md
// Uses StubLLMClient — the deterministic test double (§17: use StubLLMClient for unit tests).
import { describe, test } from 'node:test'
import { ok, strictEqual, rejects } from 'node:assert'
import { StubLLMClient } from '../stub_llm_client.js'
import type { CompletionResponse } from '../../core/protocols.js'
import { TokenLimitError } from '../../core/protocols.js'

const client = new StubLLMClient({ maxTokens: 100 })

const validRequest = {
  messages: [{ role: 'user' as const, content: 'hello' }],
  maxTokens: 50,
  temperature: 0,
}

const oversizedRequest = {
  messages: [{ role: 'user' as const, content: 'x'.repeat(500) }],
  maxTokens: 200,
  temperature: 0,
}

describe('ILLMClient conformance (§17 CLAUDE.md)', () => {
  test('complete(validRequest) returns a CompletionResponse', async () => {
    const response: CompletionResponse = await client.complete(validRequest)
    ok(typeof response.content === 'string', 'CompletionResponse.content must be a string')
    ok(response.stopReason.length > 0,       'CompletionResponse.stopReason must be non-empty')
    ok(response.usage.inputTokens >= 0,      'usage.inputTokens must be >= 0')
    ok(response.usage.outputTokens >= 0,     'usage.outputTokens must be >= 0')
  })

  test('complete(oversizedRequest) throws TokenLimitError', async () => {
    await rejects(
      () => client.complete(oversizedRequest),
      (err: unknown) => {
        ok(err instanceof TokenLimitError, 'must throw TokenLimitError — not a generic Error')
        return true
      },
      'complete() with input exceeding maxTokens must throw TokenLimitError',
    )
  })

  test('stream() yields at least one chunk before resolving', async () => {
    const chunks: unknown[] = []
    for await (const chunk of client.stream(validRequest)) {
      chunks.push(chunk)
    }
    ok(chunks.length >= 1, 'stream() must yield at least one chunk before done')
  })

  test('modelId and maxTokens are exposed on the client', () => {
    ok(client.modelId.length > 0, 'ILLMClient.modelId must be non-empty')
    ok(client.maxTokens > 0,      'ILLMClient.maxTokens must be > 0')
    strictEqual(typeof client.supportsTools, 'boolean', 'supportsTools must be boolean')
  })
})
