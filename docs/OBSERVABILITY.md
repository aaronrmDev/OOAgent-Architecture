# Observability & Safety

`OOAgent` emits structured telemetry events through the injected
`ITelemetryProvider` at every LLM call, tool call, and turn-level failure.
Wire a real provider (`ConsoleTelemetry` for development,
`OpenTelemetryProvider` for production) to see them; the default
`NullTelemetry` is a no-op, per CLAUDE.md's Null Object pattern.

## Event schema

One `agent.turn` span wraps every `respond()` call (existing). Within it:

| Event | Payload | Fires when |
|---|---|---|
| `llm.call_started` | `{round: int, vendor: LLMVendor}` | before each LLM completion request |
| `llm.call_completed` | `{round: int, vendor: LLMVendor, input_tokens: int, output_tokens: int}` | the LLM call returns successfully |
| `llm.call_failed` | `{round: int, vendor: LLMVendor, error_type: str}` | the LLM call raises |
| `tool.call_started` | `{tool: str}` | before a resolved tool's `execute()` runs |
| `tool.call_completed` | `{tool: str}` | the tool call returns successfully |
| `tool.call_failed` | `{tool: str, error_type: str}` | the tool call raises, or the tool name isn't registered (`error_type: "ToolNotFound"`) |
| `turn.failed` | `{context: str, error_type: str, recoverable: bool}` | any turn ends in failure (recoverable via `FAILURE`→`DELIVERING`→`IDLE`, or unrecoverable via a direct `reset()` to `IDLE`) |
| `turn.complete` | `{context: str, format: str, turn: int}` | a turn completes successfully (existing) |

`round` is 0-indexed per `respond()` call. `error_type` is always
`type(err).__name__`.

## Failure taxonomy

`turn.failed`'s `error_type` and `recoverable` fields map onto
`core/protocols.py`'s exception hierarchy and CLAUDE.md §16's failure modes:

| Exception | Raised by | `recoverable` | CLAUDE.md §16 response |
|---|---|---|---|
| `ConstraintViolationError` | `ConstraintEngine.assert_all()` in VALIDATING, or a pipeline step in MODELING | `True` | Halt, emit violation report, reset FSM to IDLE |
| `ScopeExitError` | domain context's pipeline / `_solve()` in SOLVING | `True` | Declare scope exit, list contexts that would satisfy the query |
| `FSMViolationError` | `SessionState.transition()` on an illegal transition | `True` or `False` (whichever handler catches it) | Always a programming error — reset to IDLE, log full FSM trace |
| `ToolExecutionError` | a tool's `execute()` (surfaces as a tool result, not a turn failure — see `tool.call_failed` instead) | n/a | Continue the turn without the tool result |
| `TokenLimitError` | an `ILLMClient` adapter, when a request exceeds the model's context window | `True` | Truncate/report per adapter; the turn ends via `_handle_failure` |
| `LifecycleError` | `respond()` called before `initialize()`, or after `dispose()` | raised before any FSM transition — no `turn.failed` event | Caller error — fix the call site |
| Any other exception (e.g. a bare `RuntimeError` from an `ILLMClient`, or a third-party `ResponseDecorator`) | provider/plugin code | `True` in MODELING/SOLVING/VALIDATING, `False` in the GATHERING prelude or DELIVERING | Emit degraded response, log via telemetry |

`recoverable=True` means `_handle_failure` caught it (MODELING, SOLVING, or
VALIDATING); `recoverable=False` means `_handle_unrecoverable_failure` caught
it (the GATHERING prelude, before a context is resolved, or DELIVERING,
after `ConstraintEngine.assert_all()` already passed). Both paths always
leave the FSM in `IDLE` before `respond()` returns.

## Wiring a real telemetry backend

```python
from ooagent.telemetry.console import ConsoleTelemetry
from ooagent.core.agent import OOAgent

agent = OOAgent(llm_client=my_client, telemetry=ConsoleTelemetry())
```

`examples/telemetry_enabled_agent.py` is a runnable end-to-end example of
`ConsoleTelemetry`. Swap `ConsoleTelemetry()` for `OpenTelemetryProvider(...)`
in production — same one-line constructor-injection pattern; the repo does
not currently ship a runnable `OpenTelemetryProvider` example. No other code
changes; `ITelemetryProvider` is the only interface `OOAgent` depends on
(DIP, CLAUDE.md §2).

## Policy hooks and redaction (already built)

`DefaultSecurityPolicy` (`src/ooagent/plugins/security/policy_engine.py`)
already covers most of what "policy hooks" and "redaction strategy" mean in
practice — scoped to **tool calls**, not the turn's original `Query.text` or
final `Artifact`. `validate_input`, `validate_output`, and `check_access` are
only ever invoked from `SecureToolWrapper.execute()`
(`plugins/security/secure_tool_wrapper.py`); there is no built-in call from
`OOAgent.respond()` into `ISecurityPolicy`. Wrapping is opt-in per tool:

- **Prompt-injection detection** — pattern-based scanning of a wrapped
  tool call's args.
- **PII detection** — pattern-based detection of common PII shapes in a
  wrapped tool call's args, logged as a warning event; `validate_input` does
  **not** redact the args before they reach `tool.execute()`. A separate
  `DefaultSecurityPolicy.mask_pii()` static method is available as a manual
  utility for callers who want to redact a string themselves — it is not
  wired into any automatic pipeline.
- **Rate limiting** — per-caller request throttling.
- **Access control** — allow/deny checks before a wrapped tool call proceeds.
- **Output validation** — pattern-based scanning of a wrapped tool call's
  return value.

Wire it via `SecureToolWrapper` (`plugins/security/secure_tool_wrapper.py`,
wraps an `ITool` to run policy checks around `execute()`) or by registering
a `SecurityPlugin` contribution — see `plugins/security/` for both. Neither
is modified by this document; this section exists so the capability is
discoverable.

## Safe defaults

`AgentConfig` (`core/protocols.py`) ships these defaults unchanged by this
document:

- `max_tool_rounds` — bounds the LLM/tool loop; the loop emits
  `[TokenBudgetExceeded]` and returns a truncated `Solution` if exceeded.
- `circuit_breaker_threshold` — consecutive LLM failures (tracked via
  `record_llm_failure()`/`record_llm_success()`) before `LifecycleManager`
  reports `"degraded"` from `health_check()`.
- `max_retries`, `turn_timeout_ms`, `tool_timeout_ms`, `specialist_timeout_ms`,
  `orchestration_timeout_ms` — these fields exist on `AgentConfig`
  (`core/protocols.py`) but are not currently read or enforced anywhere in
  `src/`. They are inert config surface, not working retry/backoff or
  timeout behavior; this document does not change that.
