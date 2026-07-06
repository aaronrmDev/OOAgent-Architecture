# .specify/gates/Makefile
# SpecDrivenWorkflow §5 — gate contract (DIP seam) for OOAgent itself.
# .github/workflows/sdd-gate.yml calls these targets by NAME. Recipes below
# are THIS repo's concrete bindings (uv/mypy/ruff/pytest/pip-audit/gitleaks).
# Contract: a gate target exits 0 on pass, non-zero on fail.

SHELL := /bin/sh
EVIDENCE := .specify/ci/out
LEDGER := .specify/ledger/audit.log

# _optional NAME : a conditional gate genuinely not applicable to this
# project (library, no DB/artifact-signing/UI/deploy pipeline) — skip
# with a logged reason (exit 0), per the SDD template's fail-open design
# for if-* gates whose recipe is not yet implemented.
define _optional
	@echo "::notice::optional gate '$(1)' not applicable to this project — skipped"; exit 0
endef

.PHONY: help \
  verify-spec typecheck lint format-check \
  sast sca secret-scan \
  migrate test coverage-gate \
  build sign e2e \
  verify-signature deploy smoke dast alerting-probe \
  ledger

help:
	@grep -E '^[a-z-]+:' $(firstword $(MAKEFILE_LIST)) | sed 's/:.*//' | sort

# ── REQUIRED gates ────────────────────────────────────────────────────────
verify-spec:        ## SDD artifacts present + traceability resolved (§6)
	bash scripts/sdd-verify-spec.sh

typecheck:          ## static type verification
	uv run mypy --strict

lint:               ## linter, zero warnings
	uv run ruff check

format-check:       ## formatter in check mode
	uv run ruff format --check

sast:               ## static security analysis (AI Safety Gate, 13 guards)
	bash scripts/ai-safety-gate.sh --verbose

sca:                ## dependency scan (A03)
	uv run --with pip-audit pip-audit

# secret-scan detects committed secrets. CI runs the dedicated gitleaks
# GitHub Action (.github/workflows/ci-core.yml); locally this recipe uses
# the gitleaks CLI if present, and otherwise skips with a pointer to CI.
secret-scan:        ## secret detection (A02)
	@command -v gitleaks >/dev/null 2>&1 && gitleaks detect --no-git -v || echo "::notice::gitleaks not installed locally — enforced in CI (ci-core.yml)"

test:               ## unit + integration + contract; coverage → $(EVIDENCE)/
	@mkdir -p $(EVIDENCE)
	PYTHONPATH=src uv run pytest tests/ --cov=ooagent --cov-report=xml:$(EVIDENCE)/coverage.xml

coverage-gate:      ## fail below constitution threshold (ARTICLE VII: 70%)
	PYTHONPATH=src uv run pytest tests/ --cov=ooagent --cov-fail-under=70 -q

ledger:             ## append COBIT audit entry → $(LEDGER) (ARTICLE III)
	@mkdir -p $(dir $(LEDGER))
	@echo "$$(date -u +%Y-%m-%dT%H:%M:%SZ) commit=$$(git rev-parse HEAD) gates=verify-spec,typecheck,lint,format-check,sast,sca,secret-scan,test,coverage-gate" >> $(LEDGER)

# ── CONDITIONAL gates (genuinely N/A for this project — see design doc) ──
migrate:            ## apply schema migrations — no DB in this project
	$(call _optional,migrate)

build:              ## build deployable/distributable (already exercised by ci-core.yml)
	uv build

sign:               ## sign artifact + provenance (A08) — no signed artifact today
	$(call _optional,sign)

e2e:                ## end-to-end suite — no UI in this project
	$(call _optional,e2e)

verify-signature:   ## verify signature before deploy — no deploy pipeline
	$(call _optional,verify-signature)

deploy:             ## deploy, gated on all-green — no deploy pipeline
	$(call _optional,deploy)

smoke:              ## post-deploy health — no deploy pipeline
	$(call _optional,smoke)

dast:               ## dynamic security scan — no deploy pipeline
	$(call _optional,dast)

alerting-probe:     ## security logging/alerting reachable (A09) — no deploy pipeline
	$(call _optional,alerting-probe)
