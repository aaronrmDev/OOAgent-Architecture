#!/usr/bin/env bash
# scripts/conformance-check.sh
# Spec Driven Development — Interface Conformance Verifier
#
# Verifies that every implementation of IAgent, IDomainContext, ITool,
# IPlugin, and ILLMClient ships the required conformance tests as mandated
# by §17 of CLAUDE.md.
#
# Exit codes:
#   0 — all conformance requirements met
#   1 — missing conformance tests detected

set -euo pipefail

FAILURES=0
PASS="✅"
FAIL="❌"

fail() { echo "[CONFORMANCE] $FAIL $*" >&2; FAILURES=$((FAILURES + 1)); }
pass() { echo "[CONFORMANCE] $PASS $*"; }
log()  { echo "[CONFORMANCE] $*"; }

log "Spec Driven Development — Conformance Check (§17 CLAUDE.md)"
echo ""

# ── IAgent conformance ──────────────────────────────────────────────────────
log "Checking IAgent conformance tests..."
IAGENT_TESTS=(
  "respond.*emptyQuery\|emptyQuery.*respond"
  "FSM.*IDLE\|IDLE.*FSM"
  "turn.*increment\|increment.*turn"
  "dispose.*idempotent\|idempotent.*dispose"
  "LifecycleError\|lifecycle.*error"
)
for pattern in "${IAGENT_TESTS[@]}"; do
  if grep -rn --include="*.ts" -iE "$pattern" testing/ 2>/dev/null | grep -q .; then
    pass "IAgent: '$pattern' conformance test present"
  else
    fail "IAgent: missing conformance test for '$pattern' (§17 CLAUDE.md)"
  fi
done

# ── IDomainContext conformance ──────────────────────────────────────────────
log "Checking IDomainContext conformance tests..."
ICONTEXT_TESTS=(
  "vocabulary.*non-empty\|vocabulary.*returns\|vocabulary\(\)"
  "problemClasses.*non-empty\|problemClasses\(\)"
  "invariants.*callable\|invariants\(\)"
  "resolveIntent.*null\|resolveIntent.*returns"
  "artifactPreferences.*preferredFormats"
)
for pattern in "${ICONTEXT_TESTS[@]}"; do
  if grep -rn --include="*.ts" -iE "$pattern" testing/ 2>/dev/null | grep -q .; then
    pass "IDomainContext: '$pattern' conformance test present"
  else
    fail "IDomainContext: missing conformance test for '$pattern' (§17 CLAUDE.md)"
  fi
done

# ── ITool conformance ───────────────────────────────────────────────────────
log "Checking ITool conformance tests..."
ITOOL_TESTS=(
  "execute.*validArgs\|validArgs.*execute"
  "ToolExecutionError\|toolexecutionerror"
  "toVendorSpec.*json\|vendorSpec.*JSON"
)
for pattern in "${ITOOL_TESTS[@]}"; do
  if grep -rn --include="*.ts" -iE "$pattern" testing/ 2>/dev/null | grep -q .; then
    pass "ITool: '$pattern' conformance test present"
  else
    fail "ITool: missing conformance test for '$pattern' (§17 CLAUDE.md)"
  fi
done

# ── ILLMClient conformance ──────────────────────────────────────────────────
log "Checking ILLMClient conformance tests..."
ILLM_TESTS=(
  "complete.*CompletionResponse\|CompletionResponse"
  "TokenLimitError\|tokenlimiterror"
  "stream.*chunk\|chunk.*stream"
)
for pattern in "${ILLM_TESTS[@]}"; do
  if grep -rn --include="*.ts" -iE "$pattern" testing/ 2>/dev/null | grep -q .; then
    pass "ILLMClient: '$pattern' conformance test present"
  else
    fail "ILLMClient: missing conformance test for '$pattern' (§17 CLAUDE.md)"
  fi
done

# ── StubLLMClient presence ──────────────────────────────────────────────────
log "Checking test doubles..."
if [[ -f "testing/stub_llm_client.ts" ]]; then
  pass "StubLLMClient present"
else
  fail "StubLLMClient missing — required for deterministic ILLMClient tests (§17)"
fi

if [[ -f "testing/null_context.ts" ]]; then
  pass "NullContext (testing re-export) present"
else
  fail "testing/null_context.ts missing — required for baseline agent-level tests (§17)"
fi

if [[ -f "testing/fixtures.ts" ]]; then
  pass "Test fixtures present"
else
  fail "testing/fixtures.ts missing — required for common Query/Solution/Artifact doubles (§17)"
fi

# ── IDomainContext implementations must have CONTEXT.md ─────────────────────
log "Checking CONTEXT.md for each IDomainContext implementation..."
for ctx_dir in contexts/*/; do
  ctx_name=$(basename "$ctx_dir")
  if [[ "$ctx_name" == "null_context.ts" ]] || [[ ! -d "$ctx_dir" ]]; then
    continue
  fi
  if [[ -f "${ctx_dir}CONTEXT.md" ]]; then
    pass "CONTEXT.md present for $ctx_name"
  else
    fail "CONTEXT.md missing for $ctx_name (§14 CLAUDE.md requires it alongside every IDomainContext)"
  fi
done

# ── core/protocols.ts must have zero runtime dependencies ───────────────────
log "Checking core/protocols.ts dependency purity..."
if grep -n "^import " core/protocols.ts 2>/dev/null | grep -v "type " | grep -q "from "; then
  fail "core/protocols.ts has runtime (non-type) imports. It must have zero runtime dependencies (§7 CLAUDE.md)."
else
  pass "core/protocols.ts has zero runtime imports"
fi

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  SDD Conformance Check — Results"
echo "════════════════════════════════════════════════════════════"
if [[ "$FAILURES" -eq 0 ]]; then
  echo "  ✅ ALL CONFORMANCE REQUIREMENTS MET"
  exit 0
else
  echo "  ❌ $FAILURES CONFORMANCE REQUIREMENT(S) UNMET"
  echo "  Write the missing tests before merging — see §17 CLAUDE.md"
  echo "════════════════════════════════════════════════════════════"
  exit 1
fi
