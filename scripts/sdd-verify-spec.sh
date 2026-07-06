#!/usr/bin/env bash
# scripts/sdd-verify-spec.sh
# SpecDrivenWorkflow — the `verify-spec` gate (.specify/gates/Makefile).
# Every specs/<NNN-slug>/ must ship spec.md + plan.md + tasks.md; every
# REQ-id in spec.md must be referenced by a TASK in tasks.md ("implements
# REQ-N/AC-M"); every TASK-id must have a paired TEST-id (1:1 count).
set -eu

FAILURES=0
SPECS_DIR="specs"

if [ ! -d "$SPECS_DIR" ]; then
  echo "::notice::${SPECS_DIR}/ does not exist — nothing to verify"
  exit 0
fi

FEATURE_DIRS=$(find "$SPECS_DIR" -mindepth 1 -maxdepth 1 -type d | sort)

if [ -z "$FEATURE_DIRS" ]; then
  echo "::notice::no feature directories under ${SPECS_DIR}/ yet — nothing to verify"
  exit 0
fi

for dir in $FEATURE_DIRS; do
  echo "Checking ${dir}..."

  for artifact in spec.md plan.md tasks.md; do
    if [ ! -f "${dir}/${artifact}" ]; then
      echo "❌ ${dir} is missing ${artifact}"
      FAILURES=$((FAILURES + 1))
    fi
  done

  if [ ! -f "${dir}/spec.md" ] || [ ! -f "${dir}/tasks.md" ]; then
    continue
  fi

  REQ_IDS=$(grep -oE '\*\*REQ-[0-9]+\*\*' "${dir}/spec.md" | tr -d '*' | sort -u || true)

  for req_id in $REQ_IDS; do
    if ! grep -q "implements ${req_id}/" "${dir}/tasks.md"; then
      echo "❌ ${dir}/spec.md: ${req_id} is an orphan — no task in tasks.md implements it"
      FAILURES=$((FAILURES + 1))
    fi
  done

  TASK_COUNT=$(grep -cE '\*\*TASK-[0-9]+\*\*' "${dir}/tasks.md" || true)
  TEST_COUNT=$(grep -cE '\*\*TEST-[0-9]+\*\*' "${dir}/tasks.md" || true)

  if [ "$TASK_COUNT" -ne "$TEST_COUNT" ]; then
    echo "❌ ${dir}/tasks.md: ${TASK_COUNT} TASK entries but ${TEST_COUNT} TEST entries — every task needs a paired test (ARTICLE VI)"
    FAILURES=$((FAILURES + 1))
  fi
done

if [ "$FAILURES" -gt 0 ]; then
  echo "verify-spec FAILED: ${FAILURES} issue(s)"
  exit 1
fi

echo "✅ verify-spec passed — all specs/ traceability resolved"
