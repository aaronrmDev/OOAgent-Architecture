// testing/conformance/agent.conformance.test.ts
// IAgent conformance suite — §17 CLAUDE.md
// These tests document the required IAgent contract.
// Tests marked todo() require a concrete OOAgent instance — implement when
// wiring a real agent in the consuming project.
import { describe, test } from 'node:test'

describe('IAgent conformance (§17 CLAUDE.md)', () => {
  // respond(emptyQuery) must return a ConstraintViolation artifact, not throw.
  test.todo('respond(emptyQuery) returns ConstraintViolation artifact — not throw')

  // FSM is IDLE before and after each successful turn.
  test.todo('FSM is IDLE before and after each complete turn')

  // turn increments by exactly 1 per successful turn.
  test.todo('SessionState.turn increments by exactly 1 per successful turn')

  // dispose() is idempotent — calling it twice must not throw.
  test.todo('dispose() is idempotent — calling twice does not throw')

  // respond() after dispose() must throw LifecycleError.
  test.todo('respond() after dispose() throws LifecycleError')
})
