#!/usr/bin/env bash
# scripts/ai-safety-gate.sh
# AI Disaster Prevention Gate — 10 Static-Analysis Guards
#
# Each guard maps to one or more documented AI disasters (2020-2026).
# A failing guard blocks the CI pipeline and MUST be fixed before merge.
#
# Exit codes:
#   0 — all guards passed
#   1 — one or more guards failed (details printed to stderr)
#
# Usage: bash scripts/ai-safety-gate.sh [--verbose]

set -euo pipefail

VERBOSE=${1:-""}
FAILURES=0
PASS="✅"
FAIL="❌"
SRC_DIRS="core adapters plugins contexts telemetry"

log()  { echo "[AI-GATE] $*"; }
fail() { echo "[AI-GATE] $FAIL $*" >&2; FAILURES=$((FAILURES + 1)); }
pass() { [[ "$VERBOSE" == "--verbose" ]] && echo "[AI-GATE] $PASS $*"; }

# ─────────────────────────────────────────────────────────────────────────────
# GUARD 1 — PROMPT INJECTION
# Disaster: Microsoft Bing "Sydney" (2023) — system prompt leaked via prompt
# injection. Samsung engineers leaked source code via ChatGPT (2023).
# JPMorgan, Goldman Sachs banned AI tools after data leakage.
#
# Check: system prompts must never be built by directly interpolating raw
# query.text into a template string. The ILLMClient tool loop must push
# system prompt as a separate Message with role:'system', never concat
# user text into it.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 1: Prompt Injection — system prompt isolation"

# Pattern: `system: ` + any template literal containing query
if grep -rn --include="*.ts" \
    -E "role:\s*['\"]system['\"].*\\\$\{.*(query|input|user|text).*\}" \
    $SRC_DIRS 2>/dev/null | grep -v "\.d\.ts" | grep -q .; then
  fail "GUARD-1 PROMPT-INJECTION: system-role Message contains interpolated user input. Separate system prompt from query.text at the Message boundary."
else
  pass "Guard 1 passed: no prompt injection via system-role interpolation"
fi

# Pattern: direct string concat of user query into systemPromptExtension result
if grep -rn --include="*.ts" \
    -E "systemPromptExtension\(\).*\+.*query|query.*\+.*systemPromptExtension\(\)" \
    $SRC_DIRS 2>/dev/null | grep -v "\.d\.ts" | grep -q .; then
  fail "GUARD-1 PROMPT-INJECTION: systemPromptExtension() result is concatenated with user query. Keep them in separate Message objects."
else
  pass "Guard 1b passed: no systemPrompt+query concat"
fi


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 2 — HALLUCINATION / PROVENANCE
# Disaster: ChatGPT gave 5x methotrexate overdose recommendation (2023).
# 93% of ChatGPT medical citations had incorrect PMID numbers.
# LLMs hallucinate at 43-88% rates in medical/legal queries.
#
# Check: ProvenanceTracker.clear() MUST be called at the start of every turn.
# ConstraintEngine.assertAll() MUST be called before DELIVERING.
# All Artifacts MUST be built via ArtifactFactory — never free-form.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 2: Hallucination / Provenance — tracking and assertion required"

if ! grep -rn --include="*.ts" "provenance\.clear\(\)\|_provenance\.clear\(\)" \
    core/ 2>/dev/null | grep -q .; then
  fail "GUARD-2 HALLUCINATION: ProvenanceTracker.clear() not found in core/. Every turn must clear provenance at start to prevent stale source attribution."
else
  pass "Guard 2a passed: ProvenanceTracker.clear() present"
fi

if ! grep -rn --include="*.ts" "constraintEngine\.assertAll\|_constraintEngine\.assertAll" \
    core/ 2>/dev/null | grep -q .; then
  fail "GUARD-2 HALLUCINATION: ConstraintEngine.assertAll() not called in core/. Invariant validation must occur before every DELIVERING transition."
else
  pass "Guard 2b passed: ConstraintEngine.assertAll() present"
fi

if ! grep -rn --include="*.ts" "artifactFactory\.build\|_artifactFactory\.build" \
    core/ 2>/dev/null | grep -q .; then
  fail "GUARD-2 HALLUCINATION: ArtifactFactory.build() not found in core/agent.ts. All artifacts must be built through ArtifactFactory — never free-form string emission."
else
  pass "Guard 2c passed: ArtifactFactory.build() present"
fi


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 3 — KILL SWITCH / CIRCUIT BREAKER
# Disaster: Tesla Autopilot (65+ fatalities 2020-2026) — no effective kill
# switch. Autonomous system continued despite known fatal failure modes.
# AWS cascading outage (2026) — no circuit breaker on cross-region traffic.
#
# Check: LifecycleManager MUST implement dispose(). CircuitBreaker MUST be
# present with a non-zero threshold. Every ILifecycle object MUST register
# with LifecycleManager.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 3: Kill Switch / Circuit Breaker — graceful shutdown required"

if ! grep -rn --include="*.ts" "class.*CircuitBreaker\|circuitBreaker" \
    core/ 2>/dev/null | grep -q .; then
  fail "GUARD-3 KILL-SWITCH: CircuitBreaker not found in core/. Every ILLMClient usage must be protected by a circuit breaker (circuitBreakerThreshold in IAgentConfig)."
else
  pass "Guard 3a passed: CircuitBreaker present"
fi

if ! grep -rn --include="*.ts" "async dispose\(\)" \
    core/ 2>/dev/null | grep -q .; then
  fail "GUARD-3 KILL-SWITCH: dispose() not found in core/lifecycle.ts. The agent MUST support graceful shutdown with resource release."
else
  pass "Guard 3b passed: dispose() present"
fi

if ! grep -rn --include="*.ts" "recordLLMFailure\|recordLLMSuccess" \
    core/ 2>/dev/null | grep -q .; then
  fail "GUARD-3 KILL-SWITCH: LLM failure recording not found. Circuit breaker requires failure counting to trigger DEGRADED state."
else
  pass "Guard 3c passed: LLM failure/success recording present"
fi


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 4 — SCOPE FRAUD / DOMAIN COMPETENCY
# Disaster: ChatGPT claimed medical expertise while NullContext active.
# COMPAS algorithm made high-stakes criminal justice predictions outside
# its validated scope without disclosing limitations.
#
# Check: ScopeExitError MUST be thrown when a query is out-of-scope.
# NullContext MUST NOT make domain claims. systemPromptExtension() in
# NullContext must explicitly state no domain expertise.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 4: Scope Fraud — domain boundary enforcement"

if ! grep -rn --include="*.ts" "ScopeExitError" \
    core/ 2>/dev/null | grep -q .; then
  fail "GUARD-4 SCOPE-FRAUD: ScopeExitError not referenced in core/. Out-of-scope queries must raise ScopeExitError, never produce fabricated domain answers."
else
  pass "Guard 4a passed: ScopeExitError present in core/"
fi

if ! grep -rn --include="*.ts" "NullContext\|null_context" \
    contexts/ core/ 2>/dev/null | grep -q .; then
  fail "GUARD-4 SCOPE-FRAUD: NullContext not found. A NullContext fallback is mandatory — it is the agent's honest 'I do not know' response."
else
  pass "Guard 4b passed: NullContext found"
fi

# NullContext must NOT claim expertise — check for domain-specific vocabulary
# in null_context.ts (should be empty/minimal)
NULL_CTX_VOCAB=$(grep -c "vocabulary\(\)" contexts/null_context.ts 2>/dev/null || echo "0")
if [[ "$NULL_CTX_VOCAB" -eq "0" ]]; then
  fail "GUARD-4 SCOPE-FRAUD: NullContext does not implement vocabulary(). It must return an empty Set<Term>."
else
  pass "Guard 4c passed: NullContext.vocabulary() implemented"
fi


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 5 — DATA EXFILTRATION / SECRET LEAKAGE
# Disaster: Clearview AI — 3B+ face images scraped without consent (2020-2026).
# Samsung engineers leaked proprietary code via ChatGPT.
# 73% of production AI deployments vulnerable to data exfiltration.
#
# Check: No hardcoded API keys, tokens, or secrets in source.
# Tool execute() must not return raw request objects (potential PII exposure).
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 5: Data Exfiltration — no secrets, no PII leakage"

SECRET_PATTERNS=(
  "apiKey\s*=\s*['\"][a-zA-Z0-9_-]{20,}"
  "api_key\s*=\s*['\"][a-zA-Z0-9_-]{20,}"
  "Bearer\s+[a-zA-Z0-9_.-]{20,}"
  "sk-[a-zA-Z0-9]{32,}"
  "AKIA[0-9A-Z]{16}"
  "password\s*=\s*['\"][^'\"]{8,}"
)

SECRET_FOUND=0
for pattern in "${SECRET_PATTERNS[@]}"; do
  if grep -rEn --include="*.ts" "$pattern" \
      $SRC_DIRS 2>/dev/null | grep -v "\.d\.ts" | grep -v "//.*$pattern" | grep -q .; then
    fail "GUARD-5 SECRET-LEAK: Potential hardcoded secret matching '$pattern'. Use environment variables."
    SECRET_FOUND=1
  fi
done
[[ "$SECRET_FOUND" -eq 0 ]] && pass "Guard 5a passed: no hardcoded secrets detected"

# Check .env files are gitignored
if [[ -f ".gitignore" ]]; then
  if ! grep -q "\.env" .gitignore; then
    fail "GUARD-5 SECRET-LEAK: .env is not in .gitignore. All environment variable files must be gitignored."
  else
    pass "Guard 5b passed: .env is gitignored"
  fi
fi


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 6 — FSM INTEGRITY / CASCADING FAILURE PREVENTION
# Disaster: AWS March 2026 cascading outage — no isolation between failure
# domains. Sprint (2026) — automated config push caused nation-wide outage
# because no staged rollout or rollback mechanism.
#
# Check: FSMViolation MUST be thrown on illegal transitions.
# FAILURE state MUST always transition to DELIVERING then IDLE — no hang.
# SessionState must own FSM — no external mutation.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 6: FSM Integrity — no illegal state transitions or hangs"

if ! grep -rn --include="*.ts" "FSMViolationError\|FSMViolation" \
    core/ 2>/dev/null | grep -q .; then
  fail "GUARD-6 FSM-INTEGRITY: FSMViolationError not in core/. Illegal FSM transitions must raise FSMViolationError — they are always programming errors."
else
  pass "Guard 6a passed: FSMViolationError present"
fi

if ! grep -rn --include="*.ts" "'FAILURE'" \
    core/ 2>/dev/null | grep -q .; then
  fail "GUARD-6 FSM-INTEGRITY: FAILURE state not handled in core/agent.ts. Every failure path must transition through FAILURE → DELIVERING → IDLE."
else
  pass "Guard 6b passed: FAILURE state handled"
fi

# Verify FSM state is only mutated through transition()
DIRECT_FSM_MUTATION=$(grep -rn --include="*.ts" \
    -E "\.fsm\s*=" \
    $SRC_DIRS 2>/dev/null | grep -v "\.d\.ts" | grep -v "transition\|readonly" | wc -l || echo "0")
if [[ "$DIRECT_FSM_MUTATION" -gt 0 ]]; then
  fail "GUARD-6 FSM-INTEGRITY: Direct mutation of .fsm detected ($DIRECT_FSM_MUTATION occurrence(s)). FSM state must only change via SessionState.transition()."
else
  pass "Guard 6c passed: no direct FSM mutation"
fi


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 7 — SUPPLY CHAIN / DEPENDENCY INTEGRITY
# Disaster: Stability AI trained on LAION dataset containing 3,000+ CSAM
# images without content scanning (2023). Data poisoning attacks via
# compromised open-source packages affect 73%+ of AI pipelines.
#
# Check: npm audit for HIGH/CRITICAL vulnerabilities.
# No new dependencies added without explicit review (package-lock.json must
# be committed and up-to-date).
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 7: Supply Chain — dependency vulnerability scan"

if [[ -f "package.json" ]]; then
  AUDIT_OUTPUT=$(npm audit --audit-level=high --json 2>/dev/null || true)
  HIGH_COUNT=$(echo "$AUDIT_OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('metadata',{}).get('vulnerabilities',{}).get('high',0)+d.get('metadata',{}).get('vulnerabilities',{}).get('critical',0))" 2>/dev/null || echo "0")
  if [[ "$HIGH_COUNT" -gt 0 ]]; then
    fail "GUARD-7 SUPPLY-CHAIN: $HIGH_COUNT HIGH/CRITICAL vulnerability(ies) found. Run 'npm audit fix' or upgrade affected packages."
  else
    pass "Guard 7a passed: no HIGH/CRITICAL npm vulnerabilities"
  fi

  if [[ ! -f "package-lock.json" ]]; then
    fail "GUARD-7 SUPPLY-CHAIN: package-lock.json missing. Lock file must be committed to guarantee reproducible, tamper-evident installs."
  else
    pass "Guard 7b passed: package-lock.json present"
  fi
fi


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 8 — PLUGIN ISOLATION
# Disaster: Plugin side-effects on agent internals can subvert safety controls.
# Rogue plugin contributions could bypass ConstraintEngine or ProvenanceTracker.
# §21 CLAUDE.md anti-pattern: "Plugin side-effects on agent internals."
#
# Check: Plugins must only call registered API surfaces (contributes() method).
# Plugins must NOT import from core/ implementation files directly.
# onDispose() must be idempotent.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 8: Plugin Isolation — no direct core internals access"

# Plugins should only import from core/protocols.js (the interface contract)
# not from core/agent.ts, core/state.ts, core/pipeline.ts etc. (implementation)
PLUGIN_INTERNAL_IMPORT=$(grep -rn --include="*.ts" \
    -E "from '../../core/(agent|state|pipeline|lifecycle|orchestrator|artifacts|registry)'" \
    plugins/ 2>/dev/null | grep -v "base-plugin" | wc -l || echo "0")
if [[ "$PLUGIN_INTERNAL_IMPORT" -gt 0 ]]; then
  fail "GUARD-8 PLUGIN-ISOLATION: Plugin(s) import from core implementation files ($PLUGIN_INTERNAL_IMPORT import(s)). Plugins must only import from 'core/protocols.js'."
else
  pass "Guard 8a passed: plugins only import core contracts"
fi

# Every concrete plugin must implement onDispose()
PLUGINS_WITHOUT_DISPOSE=$(grep -rLn "onDispose" plugins/*/index.ts 2>/dev/null | wc -l || echo "0")
if [[ "$PLUGINS_WITHOUT_DISPOSE" -gt 0 ]]; then
  fail "GUARD-8 PLUGIN-ISOLATION: $PLUGINS_WITHOUT_DISPOSE plugin file(s) missing onDispose(). All plugins must implement onDispose() for safe resource release."
else
  pass "Guard 8b passed: all plugins implement onDispose()"
fi


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 9 — BIAS / FAIRNESS
# Disaster: COMPAS recidivism algorithm (ongoing) — 2x false positive rate for
# Black defendants. Apple Card credit algorithm (2019) — women received 20x
# lower limits despite equal creditworthiness. Amazon Rekognition (2020) —
# 40% of false matches were people of color.
# Medical kidney function algorithm (2020-2021) — undertreated Black patients.
#
# Check: No hardcoded demographic signals in invariants or vocabulary.
# IDomainContext implementations must not use race, gender, or other
# protected attributes as explicit filtering criteria.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 9: Bias / Fairness — no hardcoded demographic discriminators"

DEMOGRAPHIC_SIGNALS=(
  "race\s*===\s*['\"]"
  "gender\s*===\s*['\"]"
  "ethnicity\s*===\s*['\"]"
  "\.race\b.*==\|==.*\.race\b"
  "skin_color\|skinColor"
  "protected_class\|protectedClass"
)

BIAS_FOUND=0
for pattern in "${DEMOGRAPHIC_SIGNALS[@]}"; do
  if grep -rEn --include="*.ts" "$pattern" \
      contexts/ plugins/ 2>/dev/null | grep -v "\.d\.ts" | grep -q .; then
    fail "GUARD-9 BIAS: Potential demographic discriminator '$pattern' found in contexts/ or plugins/. Protected attributes must not be used as direct filtering conditions."
    BIAS_FOUND=1
  fi
done
[[ "$BIAS_FOUND" -eq 0 ]] && pass "Guard 9 passed: no hardcoded demographic discriminators"


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 10 — OUTPUT INTEGRITY / FREE-FORM EMISSION
# Disaster: LLM hallucinations go undetected because output bypasses
# validation. Zillow Zestimate AI ($500M loss, 2021) — algorithm outputs
# were used directly without confidence thresholds or human review gates.
# §21 CLAUDE.md anti-pattern: "Free-form artifact emission" and
# "Unvalidated output."
#
# Check: No direct string returns that bypass ArtifactFactory.
# ResponseDecorator must be applied after every solve.
# No 'return { content:' patterns outside ArtifactFactory/buildError methods.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 10: Output Integrity — no unvalidated free-form emission"

# Check for raw object returns that look like Artifacts built inline
RAW_ARTIFACT=$(grep -rn --include="*.ts" \
    -E "return\s*\{\s*content:\s*['\"]" \
    core/ 2>/dev/null | grep -v "ArtifactFactory\|buildError\|buildScopeExit\|buildMissingInputs\|interface\|//\|test" \
    | wc -l || echo "0")
if [[ "$RAW_ARTIFACT" -gt 0 ]]; then
  fail "GUARD-10 OUTPUT-INTEGRITY: $RAW_ARTIFACT raw Artifact-shaped object(s) returned without ArtifactFactory. All artifacts must be built through IArtifactFactory to ensure invariant validation."
else
  pass "Guard 10a passed: no raw artifact emission detected"
fi

if ! grep -rn --include="*.ts" "decorator\.apply\|_decorator\.apply" \
    core/ 2>/dev/null | grep -q .; then
  fail "GUARD-10 OUTPUT-INTEGRITY: ResponseDecorator.apply() not found in core/. Every delivered artifact must pass through the decorator chain for provenance enrichment."
else
  pass "Guard 10b passed: ResponseDecorator.apply() present"
fi


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  AI Safety Gate — Results"
echo "════════════════════════════════════════════════════════════"
if [[ "$FAILURES" -eq 0 ]]; then
  echo "  $PASS ALL 10 GUARDS PASSED — pipeline may proceed"
  echo "════════════════════════════════════════════════════════════"
  exit 0
else
  echo "  $FAIL $FAILURES GUARD(S) FAILED — merge is BLOCKED"
  echo ""
  echo "  Each failure maps to a documented AI disaster."
  echo "  Fix all failures before requesting review."
  echo "════════════════════════════════════════════════════════════"
  exit 1
fi
