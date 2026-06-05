## Description

<!-- What does this PR do? Link to the issue: Closes #NNN -->

## Type of change

- [ ] `feat` — new feature (non-breaking)
- [ ] `fix` — bug fix (non-breaking)
- [ ] `refactor` — code change without new feature or bug fix
- [ ] `test` — conformance/unit tests only
- [ ] `docs` — documentation only
- [ ] `chore` — build, CI, or tooling
- [ ] `BREAKING` — breaking change to a `core/protocols.ts` interface

## SDD Checklist (§17 CLAUDE.md)

- [ ] Every new `IAgent` implementation ships conformance tests
- [ ] Every new `IDomainContext` ships `CONTEXT.md` (§14) + conformance tests
- [ ] Every new `ITool` ships conformance tests (valid args, ToolExecutionError, toVendorSpec)
- [ ] Every new `IPlugin` declares `contributes()`, `onRegister()`, `onDispose()`
- [ ] Breaking change to `core/protocols.ts` → version bumped (YYYY.MM.NN)
- [ ] `core/protocols.ts` still has zero runtime imports

## AI Safety Gate Self-Check

Run `bash scripts/ai-safety-gate.sh --verbose` locally before pushing.

- [ ] Guard 1 — Prompt Injection: user input never interpolated into system-role Message
- [ ] Guard 2 — Provenance: `ProvenanceTracker.clear()` and `assertAll()` called in every turn
- [ ] Guard 3 — Kill Switch: circuit breaker configured and `dispose()` implemented
- [ ] Guard 4 — Scope Fraud: `ScopeExitError` raised for out-of-scope queries
- [ ] Guard 5 — Data Exfiltration: no hardcoded secrets, `.env` gitignored
- [ ] Guard 6 — FSM Integrity: `FSMViolationError` on illegal transitions
- [ ] Guard 7 — Supply Chain: `npm audit --audit-level=high` passes
- [ ] Guard 8 — Plugin Isolation: plugins only import from `core/protocols.js`
- [ ] Guard 9 — Bias: no hardcoded demographic discriminators
- [ ] Guard 10 — Output Integrity: all artifacts built via `ArtifactFactory`

## Testing

- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes
- [ ] `npm test` passes (or `--passWithNoTests` with explanation)

## Breaking changes

<!-- If BREAKING: list every interface that changed and migration path -->
