# Observability & Safety — Design

## Purpose

Sub-project D of the OOAgent improvement backlog (A: golden path, PR #8;
B: public API, PR #9; C: testing depth, PR #10). The original proposal
asked for a structured event schema, tracing, a failure taxonomy, policy
hooks, a redaction strategy, and safe production defaults.

Investigation found the same shape of gap as B and C: the underlying
architecture is already sophisticated, but a specific piece is silently
missing. `ITelemetryProvider` (`core/protocols.py`), its three
implementations (`NullTelemetry`, `ConsoleTelemetry`,
`OpenTelemetryProvider`), and `DefaultSecurityPolicy`
(`plugins/security/policy_engine.py`, 470 lines: prompt-injection
detection, PII redaction, rate limiting, access control, output
validation — covering nearly all of "policy hooks" and "redaction
strategy" already) are all real and solid. But `core/agent.py` — the
only place that actually *calls* the telemetry provider — emits exactly
two things in the entire turn lifecycle: one `agent.turn` span and one
`turn.complete` event, **only on the success path**. Every failure
handler (`_handle_failure`, `_handle_unrecoverable_failure`) is
completely silent. A user who wires up `OpenTelemetryProvider` today
sees almost no signal, and nothing at all when something goes wrong —
precisely the case observability exists for.

**Goal:** instrument the currently-silent paths — failures, tool calls,
LLM calls — with a small, additive set of new telemetry events, and
document the resulting event schema plus the already-built
security/redaction story (currently undiscoverable) in a new
`docs/OBSERVABILITY.md`.

## Scope

**In scope:**

1. Four `self._telemetry.event(...)` call sites added to `core/agent.py`
   — `_handle_failure`, `_handle_unrecoverable_failure`, `_execute_tool`,
   and the LLM call in `_llm_tool_loop`. Every addition is a pure,
   side-effect-only insertion — no control-flow change, no new
   parameters, no changed return values or exception behavior. This is
   the highest-risk file in the codebase (composition root, the frozen
   Template Method from CLAUDE.md §10), so the bar here is: nothing
   observable changes except that telemetry now fires.
2. New event names, each with an exact payload shape (below).
3. Tests proving each new event fires with the correct payload in the
   right scenario — using a new small `_RecordingTelemetry` test double
   in `tests/core/test_agent.py`, and reusing the file's existing
   `_AlwaysFailingLLMClient`/`_boom`-decorator fixtures where they
   already exercise the exact failure paths being instrumented.
4. `docs/OBSERVABILITY.md` — the event schema, the failure taxonomy
   (mapping each event's `error_type` values to the 7 existing exception
   classes), and a pointer to `DefaultSecurityPolicy` for policy
   hooks/redaction (already built, just undocumented) — linked from
   README's "Go Deeper".

**Out of scope:**

- New spans per FSM phase (GATHERING/MODELING/SOLVING/VALIDATING/
  DELIVERING) — a bigger structural change to `respond()`'s frozen
  Template Method body than this pass's risk budget allows. The
  existing single `agent.turn` span is left as-is.
- Any change to `DefaultSecurityPolicy`, `ScopeGuardPlugin`, or any
  other plugin — they already implement policy hooks/redaction
  comprehensively; this pass only makes them discoverable via docs.
- Extending `examples/telemetry_enabled_agent.py` (sub-project A,
  already shipped/reviewed) — out of scope for this sub-project;
  readers automatically get more signal from the same example once
  this ships, without needing the example itself to change.
- Correlation/session IDs threaded through events — `Command.id` and
  `SessionState.turn` already exist as identifiers; adding a new
  cross-cutting correlation ID is a larger design decision deferred to
  a future pass if a real need emerges.

## The new events (structured schema)

```
llm.call_started    {round: int, vendor: LLMVendor}
llm.call_completed  {round: int, vendor: LLMVendor, input_tokens: int, output_tokens: int}
llm.call_failed     {round: int, vendor: LLMVendor, error_type: str}

tool.call_started    {tool: str}
tool.call_completed  {tool: str}
tool.call_failed     {tool: str, error_type: str}   # error_type == "ToolNotFound" for unregistered tools

turn.failed  {context: str, error_type: str, recoverable: bool}
             # recoverable=True  → from _handle_failure (MODELING/SOLVING/VALIDATING)
             # recoverable=False → from _handle_unrecoverable_failure (GATHERING prelude / DELIVERING)
```

`error_type` is always `type(err).__name__` — one of the 7 exception
classes already exported from `core/protocols.py`
(`ConstraintViolationError`, `FSMViolationError`, `LifecycleError`,
`ToolExecutionError`, `TokenLimitError`, `ScopeExitError`,
`OOAgentError`) or a bare `RuntimeError`/other exception's class name
for provider-level errors that don't map to one of those.

## `docs/OBSERVABILITY.md` structure

```markdown
# Observability & Safety

## Event schema
[the table above, plus which events exist today (turn.complete,
agent.turn span) vs. new in this pass]

## Failure taxonomy
[the 7 exception classes, one line each: what raises it, which event
carries it, what CLAUDE.md §16 says the response should be]

## Wiring a real telemetry backend
[ConsoleTelemetry for dev, OpenTelemetryProvider for production — both
already exist; this section just shows the one-line swap, mirroring
examples/telemetry_enabled_agent.py's existing pattern]

## Policy hooks and redaction (already built)
[DefaultSecurityPolicy: prompt-injection detection, PII redaction
patterns, rate limiting, access control, output validation — module
path, what it covers, how to wire it via SecureToolWrapper/SecurityPlugin]

## Safe defaults
[AgentConfig's existing retry/timeout/circuit-breaker defaults — this
section documents, does not change, the existing values]
```

## Testing

`tests/core/test_agent.py` gains a `_RecordingTelemetry(ITelemetryProvider)`
test double (span/counter/gauge/histogram are pass-through no-ops
matching `NullTelemetry`'s shape; `event()` appends `(name, payload)` to
a list). New tests, each constructing an `OOAgent` with
`telemetry=_RecordingTelemetry()`:

- LLM failure → `_AlwaysFailingLLMClient` (already exists in this file)
  → asserts `llm.call_failed` and `turn.failed` (`recoverable=True`)
  both fire with `error_type="RuntimeError"`.
- DELIVERING-phase failure → the existing `_boom` decorator pattern →
  asserts `turn.failed` fires with `recoverable=False`.
- Successful tool call → a new minimal stub tool + a new
  `_ToolUseLLMClient` (returns one `tool_use` response, then
  `end_turn`) → asserts `tool.call_started` then `tool.call_completed`.
- Tool raises → asserts `tool.call_failed` with the tool's real
  exception class name.
- Tool not found → asserts `tool.call_failed` with
  `error_type="ToolNotFound"`.
- Successful LLM round → asserts `llm.call_started`/`llm.call_completed`
  fire with the stub client's actual `TokenUsage` values.

## Out-of-scope confirmation

`core/agent.py`'s control flow, exception types, return values, and FSM
transitions are byte-for-byte unchanged — every new line is a
`self._telemetry.event(...)` call with no side effect beyond invoking
the (possibly no-op `NullTelemetry`) provider. `core/pipeline.py`,
`core/state.py`, `core/lifecycle.py`, and every plugin are read but not
modified.
