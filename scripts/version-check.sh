#!/usr/bin/env bash
# scripts/version-check.sh
# Validates that package.json version follows the YYYY.MM.NN convention.
# Also validates that release branch names match: release/YYYY.MM.NN
#
# YYYY = 4-digit year
# MM   = 2-digit month (01-12)
# NN   = 2-digit sequential build number within the month (01-99)
#
# Usage:
#   bash scripts/version-check.sh                  # validates package.json
#   bash scripts/version-check.sh release/2026.06.02  # validates branch name

set -euo pipefail

VERSION_REGEX="^[0-9]{4}\.(0[1-9]|1[0-2])\.(0[1-9]|[1-9][0-9])$"

fail() { echo "❌ VERSION-CHECK: $*" >&2; exit 1; }
pass() { echo "✅ VERSION-CHECK: $*"; }

# ── Branch name validation (if provided) ────────────────────────────────────
if [[ $# -gt 0 ]]; then
  BRANCH="$1"
  if [[ "$BRANCH" == release/* ]]; then
    BRANCH_VERSION="${BRANCH#release/}"
    if [[ "$BRANCH_VERSION" =~ $VERSION_REGEX ]]; then
      pass "Branch name '$BRANCH' follows YYYY.MM.NN convention"
    else
      fail "Branch name '$BRANCH' does not follow 'release/YYYY.MM.NN' convention. Example: release/2026.06.01"
    fi
  fi
fi

# ── package.json version validation ─────────────────────────────────────────
if [[ ! -f "package.json" ]]; then
  fail "package.json not found in working directory"
fi

PKG_VERSION=$(node -p "require('./package.json').version" 2>/dev/null) || \
  fail "Cannot parse package.json"

if [[ "$PKG_VERSION" =~ $VERSION_REGEX ]]; then
  pass "package.json version '$PKG_VERSION' follows YYYY.MM.NN convention"
else
  fail "package.json version '$PKG_VERSION' does not follow YYYY.MM.NN convention. Expected format: YYYY.MM.NN (e.g. 2026.06.01)"
fi

# ── Year sanity check ────────────────────────────────────────────────────────
YEAR="${PKG_VERSION%%.*}"
CURRENT_YEAR=$(date +%Y)
if [[ "$YEAR" -lt 2026 ]]; then
  fail "Version year $YEAR is in the past. Versions must use the current or future year."
fi
if [[ "$YEAR" -gt $((CURRENT_YEAR + 1)) ]]; then
  fail "Version year $YEAR is more than 1 year in the future. Check version."
fi

pass "All version checks passed — version: $PKG_VERSION"
