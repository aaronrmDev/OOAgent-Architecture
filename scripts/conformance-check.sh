#!/usr/bin/env bash
# scripts/conformance-check.sh — SDD Conformance Check (§17 CLAUDE.md)
#
# Introspects ACTUAL pytest test IDs via `pytest --collect-only`, rather than
# regexing raw file text against hardcoded patterns. This is the direct fix
# for the brittle-regex bug in the prior (TypeScript-era) version of this
# script, where its expected patterns didn't match the real test wording and
# a CI run kept failing even after a commit claimed to "fix" it.
set -euo pipefail

echo "[CONFORMANCE] Spec Driven Development — Conformance Check (§17 CLAUDE.md)"
echo ""

COLLECTED=$(PYTHONPATH=src python -m pytest tests/conformance/ --collect-only -q 2>/dev/null)
FAILURES=0

check() {
  local pattern="$1"
  local description="$2"
  if echo "$COLLECTED" | grep -qiE "$pattern"; then
    echo "[CONFORMANCE] ✅ $description"
  else
    echo "[CONFORMANCE] ❌ missing conformance test for: $description"
    FAILURES=$((FAILURES + 1))
  fi
}

echo "[CONFORMANCE] Checking IAgent conformance tests..."
check "empty.*query|respond.*constraint" "IAgent: respond(emptyQuery) -> ConstraintViolation artifact"
check "fsm.*idle" "IAgent: FSM is IDLE before and after each complete turn"
check "turn.*increment" "IAgent: SessionState.turn increments by exactly 1"
check "dispose.*idempotent" "IAgent: dispose() is idempotent"
check "respond.*after.*dispose|lifecycle.*error" "IAgent: respond() after dispose() throws LifecycleError"

echo "[CONFORMANCE] Checking IDomainContext conformance tests..."
check "vocabulary.*non.empty" "IDomainContext: vocabulary() returns non-empty set"
check "problem.*class.*non.empty" "IDomainContext: problem_classes() returns non-empty set"
check "invariants.*callable" "IDomainContext: invariants() are callable without throwing"
check "resolve.*intent.*none|resolve.*intent.*unrecognized" "IDomainContext: resolve_intent returns None for unrecognized query"
check "artifact.*preferences.*non.empty|preferred.*formats.*non.empty" "IDomainContext: artifact_preferences().preferred_formats is non-empty"

echo "[CONFORMANCE] Checking ITool conformance tests..."
check "execute.*valid.*args" "ITool: execute(valid_args) returns without throwing"
check "tool.*execution.*error" "ITool: execute(invalid_args) throws ToolExecutionError"
check "to.*vendor.*spec.*json" "ITool: to_vendor_spec() returns valid JSON"
check "name.*and.*description.*non.empty" "ITool: name and description are non-empty strings"

echo "[CONFORMANCE] Checking ILLMClient conformance tests..."
check "complete.*completion.*response|valid.*request.*completion" "ILLMClient: complete(valid_request) returns CompletionResponse"
check "token.*limit.*error" "ILLMClient: complete(oversized_request) throws TokenLimitError"
check "stream.*chunk" "ILLMClient: stream() yields at least one chunk"

echo "[CONFORMANCE] Checking test doubles..."
if [ -f tests/stub_llm_client.py ]; then
  echo "[CONFORMANCE] ✅ StubLLMClient present"
else
  echo "[CONFORMANCE] ❌ StubLLMClient missing"
  FAILURES=$((FAILURES + 1))
fi

if [ -f tests/null_context.py ]; then
  echo "[CONFORMANCE] ✅ NullContext (testing re-export) present"
else
  echo "[CONFORMANCE] ❌ NullContext (testing re-export) missing"
  FAILURES=$((FAILURES + 1))
fi

if [ -f tests/fixtures.py ]; then
  echo "[CONFORMANCE] ✅ Test fixtures present"
else
  echo "[CONFORMANCE] ❌ Test fixtures missing"
  FAILURES=$((FAILURES + 1))
fi

echo "[CONFORMANCE] Checking core/protocols.py dependency purity..."
if grep -qE '^\s*(import|from)\s+(?!(abc|typing|dataclasses|enum|collections))\w' src/ooagent/core/protocols.py 2>/dev/null; then
  echo "[CONFORMANCE] ❌ core/protocols.py has non-stdlib imports"
  FAILURES=$((FAILURES + 1))
else
  echo "[CONFORMANCE] ✅ core/protocols.py has zero runtime imports"
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  SDD Conformance Check — Results"
echo "════════════════════════════════════════════════════════════"
if [ "$FAILURES" -gt 0 ]; then
  echo "  ❌ $FAILURES CONFORMANCE REQUIREMENT(S) UNMET"
  echo "  Write the missing tests before merging — see §17 CLAUDE.md"
  echo "════════════════════════════════════════════════════════════"
  exit 1
fi
echo "  ✅ All conformance requirements met"
echo "════════════════════════════════════════════════════════════"
