// @ooagent/copilot-extension — OOAgent GitHub Copilot Extension
// Implements the GitHub Copilot Extensions API so OOAgent appears as a
// first-class Copilot agent in VS Code, GitHub.com, and JetBrains IDEs.
//
// Copilot Extensions API reference:
//   https://docs.github.com/en/copilot/building-copilot-extensions
//
// Architecture:
//   GitHub Copilot → HTTPS (SSE) → CopilotExtensionServer → OOAgent.respond()
//
// Installation:
//   1. Deploy this server (Vercel, Railway, Render, etc.)
//   2. Register as a GitHub App with Copilot Extension capabilities
//   3. Install the App on your GitHub org
//   4. @ooagent mention in Copilot Chat routes to this server

export { CopilotExtensionServer }    from './server.js'
export { CopilotExtensionPlugin }    from './plugin.js'
export { CopilotPayloadVerifier }    from './verifier.js'
export type { CopilotExtensionConfig } from './server.js'
