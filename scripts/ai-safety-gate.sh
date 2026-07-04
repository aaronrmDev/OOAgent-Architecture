#!/usr/bin/env bash
# scripts/ai-safety-gate.sh
# AI Disaster Prevention Gate — 13 Static-Analysis Guards
#
# Each guard maps to one or more documented AI disasters (2020-2026).
# A failing guard blocks the CI pipeline and MUST be fixed before merge.
#
# Ported from the TypeScript-era version of this script: guards now scan
# `.py` sources under src/ooagent/ instead of `.ts` sources at the repo
# root. Guard names, rationale, and the pass/fail contract are unchanged.
# Where an existing tool (mypy --strict, ruff) already enforces part of a
# guard's intent, the guard is kept as a belt-and-suspenders check — it is
# noted inline rather than removed, since these are safety gates, not
# style lints, and a missing/misconfigured tool run must not silently
# remove the check.
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
SRC_DIRS="src/ooagent/core src/ooagent/adapters src/ooagent/plugins src/ooagent/contexts src/ooagent/telemetry"

log()  { echo "[AI-GATE] $*"; }
fail() { echo "[AI-GATE] $FAIL $*" >&2; FAILURES=$((FAILURES + 1)); }
pass() {
  # NOTE: must not let `set -e` see the exit status of a false `[[ ]]` test
  # here — that would abort the whole gate on the very first *passing*
  # guard whenever run without --verbose (the original TS script had this
  # exact latent bug: `[[ cond ]] && echo ...` returns 1 when cond is
  # false, and a bare `pass(...)` call in an else-branch is not exempt from
  # `set -e`). Always return 0 regardless of verbosity.
  [[ "$VERBOSE" == "--verbose" ]] && echo "[AI-GATE] $PASS $*"
  return 0
}

# ─────────────────────────────────────────────────────────────────────────────
# GUARD 1 — PROMPT INJECTION
# Disaster: Microsoft Bing "Sydney" (2023) — system prompt leaked via prompt
# injection. Samsung engineers leaked source code via ChatGPT (2023).
# JPMorgan, Goldman Sachs banned AI tools after data leakage.
#
# Check: system prompts must never be built by directly interpolating raw
# query.text into an f-string. The ILLMClient tool loop must push the
# system prompt as a separate Message(role="system", ...), never concat
# user text into it.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 1: Prompt Injection — system prompt isolation"

# Pattern: `role="system"` + any f-string containing query/input/user/text
if grep -rn --include="*.py" \
    -E "role\s*=\s*['\"]system['\"].*f['\"].*\{.*(query|input|user|text).*\}" \
    $SRC_DIRS 2>/dev/null | grep -q .; then
  fail "GUARD-1 PROMPT-INJECTION: system-role Message contains interpolated user input. Separate system prompt from query.text at the Message boundary."
else
  pass "Guard 1 passed: no prompt injection via system-role interpolation"
fi

# Pattern: direct string concat of user query into system_prompt_extension() result
if grep -rn --include="*.py" \
    -E "system_prompt_extension\(\).*\+.*query|query.*\+.*system_prompt_extension\(\)" \
    $SRC_DIRS 2>/dev/null | grep -q .; then
  fail "GUARD-1 PROMPT-INJECTION: system_prompt_extension() result is concatenated with user query. Keep them in separate Message objects."
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
# ConstraintEngine.assert_all() MUST be called before DELIVERING.
# All Artifacts MUST be built via ArtifactFactory — never free-form.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 2: Hallucination / Provenance — tracking and assertion required"

if ! grep -rn --include="*.py" "provenance\.clear\(\)\|_provenance\.clear\(\)" \
    src/ooagent/core/ 2>/dev/null | grep -q .; then
  fail "GUARD-2 HALLUCINATION: ProvenanceTracker.clear() not found in core/. Every turn must clear provenance at start to prevent stale source attribution."
else
  pass "Guard 2a passed: ProvenanceTracker.clear() present"
fi

if ! grep -rn --include="*.py" "constraint_engine\.assert_all\|_constraint_engine\.assert_all" \
    src/ooagent/core/ 2>/dev/null | grep -q .; then
  fail "GUARD-2 HALLUCINATION: ConstraintEngine.assert_all() not called in core/. Invariant validation must occur before every DELIVERING transition."
else
  pass "Guard 2b passed: ConstraintEngine.assert_all() present"
fi

if ! grep -rn --include="*.py" "artifact_factory\.build\|_artifact_factory\.build" \
    src/ooagent/core/ 2>/dev/null | grep -q .; then
  fail "GUARD-2 HALLUCINATION: ArtifactFactory.build() not found in core/agent.py. All artifacts must be built through ArtifactFactory — never free-form string emission."
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

if ! grep -rn --include="*.py" "class.*CircuitBreaker\|circuit_breaker" \
    src/ooagent/core/ 2>/dev/null | grep -q .; then
  fail "GUARD-3 KILL-SWITCH: CircuitBreaker not found in core/. Every ILLMClient usage must be protected by a circuit breaker (circuit_breaker_threshold in IAgentConfig)."
else
  pass "Guard 3a passed: CircuitBreaker present"
fi

if ! grep -rn --include="*.py" "async def dispose\(\)" \
    src/ooagent/core/ 2>/dev/null | grep -q .; then
  fail "GUARD-3 KILL-SWITCH: dispose() not found in core/lifecycle.py. The agent MUST support graceful shutdown with resource release."
else
  pass "Guard 3b passed: dispose() present"
fi

if ! grep -rn --include="*.py" "record_llm_failure\|record_llm_success" \
    src/ooagent/core/ 2>/dev/null | grep -q .; then
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
# NullContext MUST NOT make domain claims. system_prompt_extension() in
# NullContext must explicitly state no domain expertise.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 4: Scope Fraud — domain boundary enforcement"

if ! grep -rn --include="*.py" "ScopeExitError" \
    src/ooagent/core/ 2>/dev/null | grep -q .; then
  fail "GUARD-4 SCOPE-FRAUD: ScopeExitError not referenced in core/. Out-of-scope queries must raise ScopeExitError, never produce fabricated domain answers."
else
  pass "Guard 4a passed: ScopeExitError present in core/"
fi

if ! grep -rn --include="*.py" "NullContext\|null_context" \
    src/ooagent/contexts/ src/ooagent/core/ 2>/dev/null | grep -q .; then
  fail "GUARD-4 SCOPE-FRAUD: NullContext not found. A NullContext fallback is mandatory — it is the agent's honest 'I do not know' response."
else
  pass "Guard 4b passed: NullContext found"
fi

# NullContext must NOT claim expertise — check for domain-specific vocabulary
# in null_context.py (should be empty/minimal)
NULL_CTX_VOCAB=$(grep -c "def vocabulary" src/ooagent/contexts/null_context.py 2>/dev/null || echo "0")
if [[ "$NULL_CTX_VOCAB" -eq "0" ]]; then
  fail "GUARD-4 SCOPE-FRAUD: NullContext does not implement vocabulary(). It must return an empty set[Term]."
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
  "api_key\s*=\s*['\"][a-zA-Z0-9_-]{20,}"
  "apiKey\s*=\s*['\"][a-zA-Z0-9_-]{20,}"
  "Bearer\s+[a-zA-Z0-9_.-]{20,}"
  "sk-[a-zA-Z0-9]{32,}"
  "AKIA[0-9A-Z]{16}"
  "password\s*=\s*['\"][^'\"]{8,}"
)

SECRET_FOUND=0
for pattern in "${SECRET_PATTERNS[@]}"; do
  if grep -rEn --include="*.py" "$pattern" \
      $SRC_DIRS 2>/dev/null | grep -v "^\s*#.*$pattern" | grep -q .; then
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
# Check: FSMViolationError MUST be thrown on illegal transitions.
# FAILURE state MUST always transition to DELIVERING then IDLE — no hang.
# SessionState must own FSM — no external mutation.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 6: FSM Integrity — no illegal state transitions or hangs"

if ! grep -rn --include="*.py" "FSMViolationError\|FSMViolation" \
    src/ooagent/core/ 2>/dev/null | grep -q .; then
  fail "GUARD-6 FSM-INTEGRITY: FSMViolationError not in core/. Illegal FSM transitions must raise FSMViolationError — they are always programming errors."
else
  pass "Guard 6a passed: FSMViolationError present"
fi

if ! grep -rn --include="*.py" '"FAILURE"' \
    src/ooagent/core/ 2>/dev/null | grep -q .; then
  fail "GUARD-6 FSM-INTEGRITY: FAILURE state not handled in core/agent.py. Every failure path must transition through FAILURE → DELIVERING → IDLE."
else
  pass "Guard 6b passed: FAILURE state handled"
fi

# Verify FSM state is only mutated through transition()
# (mypy --strict already forbids untyped attribute access, but this guard
# additionally catches an *encapsulation* violation mypy does not check:
# a caller reaching past the SessionState.transition() gate to poke .fsm
# directly — belt-and-suspenders alongside static typing.)
DIRECT_FSM_MUTATION=$(grep -rn --include="*.py" \
    -E "\.fsm\s*=" \
    $SRC_DIRS 2>/dev/null | grep -v "transition\|property" | wc -l | xargs || true)
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
# Check: pip-audit (if installed) for HIGH/CRITICAL vulnerabilities.
# No new dependencies added without explicit review (uv.lock must be
# committed and up-to-date).
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 7: Supply Chain — dependency vulnerability scan"

if [[ -f "pyproject.toml" ]]; then
  if command -v pip-audit >/dev/null 2>&1; then
    AUDIT_OUTPUT=$(pip-audit --format=json 2>/dev/null || true)
    HIGH_COUNT=$(echo "$AUDIT_OUTPUT" | python -c "import sys,json; d=json.load(sys.stdin); deps=d if isinstance(d,list) else d.get('dependencies',[]); print(sum(len(x.get('vulns',[])) for x in deps))" 2>/dev/null || echo "0")
    if [[ "$HIGH_COUNT" -gt 0 ]]; then
      fail "GUARD-7 SUPPLY-CHAIN: $HIGH_COUNT known vulnerability(ies) found by pip-audit. Run 'pip-audit --fix' or upgrade affected packages."
    else
      pass "Guard 7a passed: no known vulnerabilities reported by pip-audit"
    fi
  else
    pass "Guard 7a skipped: pip-audit not installed (install via 'pip install pip-audit' to enable this check in CI)"
  fi

  if [[ ! -f "uv.lock" ]]; then
    fail "GUARD-7 SUPPLY-CHAIN: uv.lock missing. Lock file must be committed to guarantee reproducible, tamper-evident installs."
  else
    pass "Guard 7b passed: uv.lock present"
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
# on_dispose() must be idempotent.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 8: Plugin Isolation — no direct core internals access"

# Plugins should only import from ooagent.core.protocols (the interface
# contract), not from ooagent.core.agent / .state / .pipeline etc.
# (implementation). src/ooagent/plugins/__init__.py is the package barrel
# that wires PluginRegistry (itself housed in core/registry.py in this
# port) for framework use — analogous to the base-plugin exclusion in the
# original TS guard, it is not a concrete IPlugin implementation reaching
# into agent internals, so it is excluded here.
PLUGIN_INTERNAL_IMPORT=$(grep -rn --include="*.py" \
    -E "from ooagent\.core\.(agent|state|pipeline|lifecycle|orchestrator|artifacts|registry) import" \
    src/ooagent/plugins/ 2>/dev/null | grep -v "base_plugin.py" | grep -v "plugins/__init__.py" | wc -l | xargs || true)
if [[ "$PLUGIN_INTERNAL_IMPORT" -gt 0 ]]; then
  fail "GUARD-8 PLUGIN-ISOLATION: Plugin(s) import from core implementation files ($PLUGIN_INTERNAL_IMPORT import(s)). Plugins must only import from 'ooagent.core.protocols'."
else
  pass "Guard 8a passed: plugins only import core contracts"
fi

# Every concrete plugin must implement on_dispose()
PLUGINS_WITHOUT_DISPOSE=$(grep -rLn "on_dispose" src/ooagent/plugins/*/__init__.py 2>/dev/null | wc -l | xargs || true)
if [[ "$PLUGINS_WITHOUT_DISPOSE" -gt 0 ]]; then
  fail "GUARD-8 PLUGIN-ISOLATION: $PLUGINS_WITHOUT_DISPOSE plugin file(s) missing on_dispose(). All plugins must implement on_dispose() for safe resource release."
else
  pass "Guard 8b passed: all plugins implement on_dispose()"
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
  "race\s*==\s*['\"]"
  "gender\s*==\s*['\"]"
  "ethnicity\s*==\s*['\"]"
  "\.race\b.*==\|==.*\.race\b"
  "skin_color\|skinColor"
  "protected_class\|protectedClass"
)

BIAS_FOUND=0
for pattern in "${DEMOGRAPHIC_SIGNALS[@]}"; do
  if grep -rEn --include="*.py" "$pattern" \
      src/ooagent/contexts/ src/ooagent/plugins/ 2>/dev/null | grep -q .; then
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
# Check: No direct Artifact(...) construction that bypasses ArtifactFactory.
# ResponseDecorator must be applied after every solve.
# No raw '{"content": ...}' returns outside ArtifactFactory/build_error methods.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 10: Output Integrity — no unvalidated free-form emission"

# Check for raw Artifact(...) construction outside core/artifacts.py (the
# ArtifactFactory implementation) and for raw dict-shaped Artifact returns.
RAW_ARTIFACT=$(grep -rn --include="*.py" \
    -E "Artifact\(|return\s*\{\s*[\"']content[\"']\s*:" \
    src/ooagent/core/ 2>/dev/null | grep -v "artifacts.py" \
    | grep -v "ArtifactFactory\|build_error\|build_scope_exit\|build_missing_inputs\|#\|test" \
    | wc -l | xargs || true)
if [[ "$RAW_ARTIFACT" -gt 0 ]]; then
  fail "GUARD-10 OUTPUT-INTEGRITY: $RAW_ARTIFACT raw Artifact-shaped object(s) returned without ArtifactFactory. All artifacts must be built through IArtifactFactory to ensure invariant validation."
else
  pass "Guard 10a passed: no raw artifact emission detected"
fi

if ! grep -rn --include="*.py" "decorator\.apply\|_decorator\.apply" \
    src/ooagent/core/ 2>/dev/null | grep -q .; then
  fail "GUARD-10 OUTPUT-INTEGRITY: ResponseDecorator.apply() not found in core/. Every delivered artifact must pass through the decorator chain for provenance enrichment."
else
  pass "Guard 10b passed: ResponseDecorator.apply() present"
fi


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 11 — OWASP LLM TOP 10 / SECURITY PLUGIN PRESENCE
# Standard: OWASP LLM Top 10 (2025) — the 10 most critical LLM security risks.
# NIST AI RMF — Govern/Map/Measure/Manage controls.
#
# Check: SecurityPlugin must be present in plugins/.
# ISecurityPolicy interface must be defined.
# SecureToolWrapper must intercept tool calls.
# Prompt injection patterns must be enumerated (LLM01).
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 11: OWASP LLM Top 10 — SecurityPlugin compliance"

if ! grep -rn --include="*.py" "SecurityPlugin" \
    src/ooagent/plugins/ 2>/dev/null | grep -q .; then
  fail "GUARD-11 OWASP-LLM: SecurityPlugin not found in plugins/. OWASP LLM Top 10 compliance requires a SecurityPlugin wrapping all ITool executions."
else
  pass "Guard 11a passed: SecurityPlugin found"
fi

if ! grep -rn --include="*.py" "ISecurityPolicy" \
    src/ooagent/plugins/ 2>/dev/null | grep -q .; then
  fail "GUARD-11 OWASP-LLM: ISecurityPolicy interface not found. OWASP LLM compliance requires a formal security policy contract (DIP)."
else
  pass "Guard 11b passed: ISecurityPolicy interface found"
fi

if ! grep -rn --include="*.py" "SecureToolWrapper" \
    src/ooagent/plugins/ 2>/dev/null | grep -q .; then
  fail "GUARD-11 OWASP-LLM: SecureToolWrapper not found. All ITool.execute() calls must pass through the security gate (LLM01, LLM02, LLM04, LLM07)."
else
  pass "Guard 11c passed: SecureToolWrapper found"
fi

# LLM01: verify injection patterns are defined
if ! grep -rn --include="*.py" "PROMPT_INJECTION\|blocked_patterns\|injection_patterns\|INJECTION_PATTERNS" \
    src/ooagent/plugins/security/ 2>/dev/null | grep -q .; then
  fail "GUARD-11 OWASP-LLM01: No prompt injection patterns defined in plugins/security/. LLM01 mitigation requires explicit pattern list."
else
  pass "Guard 11d passed: LLM01 prompt injection patterns defined"
fi

# LLM04: verify rate limiting is implemented
if ! grep -rn --include="*.py" "max_calls_per_minute\|max_calls_per_hour\|max_input_tokens\|rate_limit" \
    src/ooagent/plugins/security/ 2>/dev/null | grep -q .; then
  fail "GUARD-11 OWASP-LLM04: No rate limiting in plugins/security/. LLM04 (Model DoS) mitigation requires per-agent call limits."
else
  pass "Guard 11e passed: LLM04 rate limiting implemented"
fi


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 12 — ZERO TRUST / RBAC / ACCESS CONTROL
# Standard: NIST SP 800-207 (Zero Trust Architecture).
# OWASP API Top 10: API1 (Broken Object Level Auth), API2 (Broken Auth).
# SOC 2 Type II: CC6.1 (Logical access), CC6.2 (Access grants).
#
# Check: Every tool call must be authorized (check_access before execute).
# allowed_agent_ids and allowed_tools must be configurable (least privilege).
# RBAC must be a controllable flag — not hard-coded to true or false.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 12: Zero Trust / RBAC — access control on every tool call"

if ! grep -rn --include="*.py" "check_access\|rbac_enabled\|allowed_agent_ids\|allowed_tools" \
    src/ooagent/plugins/security/ 2>/dev/null | grep -q .; then
  fail "GUARD-12 ZERO-TRUST: No access control found in plugins/security/. Zero Trust requires check_access() before every tool execution (NIST SP 800-207)."
else
  pass "Guard 12a passed: Zero Trust check_access present"
fi

# Verify the wrapper calls check_access before execute
if ! grep -rn --include="*.py" "check_access" \
    src/ooagent/plugins/security/secure_tool_wrapper.py 2>/dev/null | grep -q .; then
  fail "GUARD-12 ZERO-TRUST: SecureToolWrapper does not call check_access(). Access check must occur before every tool execute() call."
else
  pass "Guard 12b passed: SecureToolWrapper calls check_access()"
fi

# SOC 2 CC6.2: audit log must exist
if ! grep -rn --include="*.py" "audit_log\|record\b" \
    src/ooagent/plugins/security/ 2>/dev/null | grep -q .; then
  fail "GUARD-12 SOC2-CC6.2: No audit log in plugins/security/. SOC 2 CC6.2 requires recording every access control decision."
else
  pass "Guard 12c passed: SOC2 CC6.2 audit log present"
fi


# ─────────────────────────────────────────────────────────────────────────────
# GUARD 13 — PII / GDPR / HIPAA DATA PROTECTION
# Standard: GDPR Article 25 (Privacy by Design), HIPAA 164.312(b),
# PCI DSS 4.0 Req 10.2, ISO 27001 A.18.1.
# OWASP LLM06: Sensitive Information Disclosure.
#
# Check: PII masking must be implemented (email, phone, SSN, CC, API keys).
# Audit records must NOT include raw PII (inputs excluded by default).
# retention_days must be configurable (GDPR right to erasure).
# PII detection patterns must cover at least: email, phone, SSN, CC.
# ─────────────────────────────────────────────────────────────────────────────
log "Guard 13: PII / GDPR / HIPAA — data protection compliance"

if ! grep -rn --include="*.py" "mask_pii\|pii_masking\|PII_PATTERNS\|REDACTED" \
    src/ooagent/plugins/security/ 2>/dev/null | grep -q .; then
  fail "GUARD-13 GDPR-PII: No PII masking in plugins/security/. GDPR Art.25 requires data minimization — PII must be masked before entering audit logs."
else
  pass "Guard 13a passed: PII masking implemented"
fi

# Verify email PII pattern is present
if ! grep -rn --include="*.py" -iE "email.*(pattern|regex)|@.*\\..*re\\.compile|EMAIL_RE|email.*re\\.compile" \
    src/ooagent/plugins/security/ 2>/dev/null | grep -q .; then
  fail "GUARD-13 GDPR-PII: No email detection pattern in plugins/security/. Email addresses are personal data under GDPR Art.4(1) and must be detected for masking."
else
  pass "Guard 13b passed: email PII pattern present"
fi

# Verify retention_days is configurable (not hard-coded forever)
if ! grep -rn --include="*.py" "retention_days" \
    src/ooagent/plugins/security/ 2>/dev/null | grep -q .; then
  fail "GUARD-13 GDPR-PII: No retention_days in plugins/security/SecurityPolicy. GDPR Art.5(1)(e) requires data retention limits — hard-coded unlimited retention is non-compliant."
else
  pass "Guard 13c passed: retention_days configurable"
fi

# LLM06: audit records must not include raw inputs by default
if grep -rn --include="*.py" \
    -E "include_input\s*=\s*True|include_output\s*=\s*True" \
    src/ooagent/plugins/security/ 2>/dev/null | grep -i "default" | grep -q .; then
  fail "GUARD-13 GDPR-LLM06: Default SecurityPolicy includes raw input/output in audit log. Default must be False to prevent PII capture (GDPR Art.25, LLM06)."
else
  pass "Guard 13d passed: audit log excludes raw I/O by default"
fi


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  AI Safety Gate — Results"
echo "════════════════════════════════════════════════════════════"
if [[ "$FAILURES" -eq 0 ]]; then
  echo "  $PASS ALL 13 GUARDS PASSED — pipeline may proceed"
  echo "════════════════════════════════════════════════════════════"
  exit 0
else
  echo "  $FAIL $FAILURES GUARD(S) FAILED — merge is BLOCKED"
  echo ""
  echo "  Each failure maps to a documented AI disaster or compliance requirement."
  echo "  Fix all failures before requesting review."
  echo "════════════════════════════════════════════════════════════"
  exit 1
fi
