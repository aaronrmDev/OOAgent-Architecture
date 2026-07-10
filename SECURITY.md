# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in OOAgent, please report it
privately rather than opening a public issue:

1. Use GitHub's [private vulnerability reporting](https://github.com/aaronrmDev/OOAgent-Architecture/security/advisories/new)
   feature (Security tab → Report a vulnerability) if enabled for this
   repository.
2. If private reporting isn't available, open an issue with minimal
   detail (do not include exploit specifics) and request a private
   channel.

We aim to acknowledge reports within 5 business days and to provide a
remediation timeline once the report is triaged.

## Supported Versions

This project uses `YYYY.MM.NN` versioning (see `CONTRIBUTORS.md`).
Security fixes are backported to the current and immediately prior
month's release. Older releases are not maintained.

## What Counts as a Security Issue Here

This framework already ships real security-adjacent tooling as part of
its normal architecture, not as a response to this policy:

- **AI Safety Gate** — 13 automated guards (`scripts/ai-safety-gate.sh`)
  that every contribution must pass before merge (see `CONTRIBUTORS.md`).
- **`DefaultSecurityPolicy`** (`src/ooagent/plugins/security/`) — prompt-
  injection detection, PII-warning logging, rate limiting, access
  control, and output validation for any `ITool` wrapped in
  `SecureToolWrapper` (see `docs/OBSERVABILITY.md`'s "Policy hooks and
  redaction (already built)" section for exactly what this does and does
  not cover today).

This policy is about **reporting a new vulnerability you've found** —
a gap in the framework's own code, a bypass of the AI Safety Gate, or a
flaw in `DefaultSecurityPolicy`'s checks — not a description of what's
already built (that's `docs/OBSERVABILITY.md` and `CONTRIBUTORS.md`'s job).
