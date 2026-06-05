// @ooagent/copilot-extension/verifier.ts
// Verifies GitHub Copilot Extension webhook signatures.
// Every incoming request from GitHub must pass signature verification
// before the payload is processed — prevents spoofing attacks.
//
// Reference: https://docs.github.com/en/copilot/building-copilot-extensions/building-a-copilot-agent-for-your-copilot-extension

import { createHmac, timingSafeEqual } from 'node:crypto'

export class CopilotPayloadVerifier {
  private readonly _secret: string

  constructor(webhookSecret: string) {
    this._secret = webhookSecret
  }

  /**
   * Verifies the GitHub signature header against the raw request body.
   * Throws if the signature is invalid or missing.
   *
   * @param signature - Value of 'X-GitHub-Token' or 'Github-Public-Key-Signature' header
   * @param body - Raw request body (Buffer or string)
   */
  verify(signature: string | undefined, body: Buffer | string): void {
    if (!signature) {
      throw new Error('Missing GitHub signature header')
    }

    const bodyBuf = Buffer.isBuffer(body) ? body : Buffer.from(body, 'utf8')
    const expected = createHmac('sha256', this._secret)
      .update(bodyBuf)
      .digest('hex')

    const sigBuf = Buffer.from(signature.replace(/^sha256=/, ''), 'hex')
    const expBuf = Buffer.from(expected, 'hex')

    if (sigBuf.length !== expBuf.length || !timingSafeEqual(sigBuf, expBuf)) {
      throw new Error('Invalid GitHub signature — request rejected')
    }
  }

  /**
   * Extracts the GitHub token from the Authorization header for API calls.
   */
  static extractToken(authHeader: string | undefined): string | null {
    if (!authHeader?.startsWith('Bearer ')) return null
    return authHeader.slice('Bearer '.length)
  }
}
