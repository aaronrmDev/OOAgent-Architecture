# Roadmap

## Shipped

A comprehensive improvement backlog (positioning, onboarding,
architecture clarity, API surface, testing depth, observability,
ecosystem/extension guides, repo process maturity) was decomposed into
six sub-projects, A through F:

- **A. Golden Path & Positioning** — README rewrite, `examples/` folder.
  [Design spec](docs/superpowers/specs/2026-07-06-golden-path-examples-design.md).
- **B. Public API & Stability Contract** — curated top-level barrel
  export, `docs/PUBLIC_API.md`.
  [Design spec](docs/superpowers/specs/2026-07-06-public-api-stability-design.md).
- **C. Testing & Reliability Depth** — LLM adapter behavior-matrix
  tests, `docs/TESTING.md`.
  [Design spec](docs/superpowers/specs/2026-07-06-testing-reliability-depth-design.md).
- **D. Observability & Safety** — telemetry events on previously-silent
  failure paths, `docs/OBSERVABILITY.md`.
  [Design spec](docs/superpowers/specs/2026-07-08-observability-safety-design.md).
- **E. Ecosystem & Extension Guides** — worked `CONTEXT.md` example,
  `docs/EXTENDING.md`.
  [Design spec](docs/superpowers/specs/2026-07-09-ecosystem-extension-guides-design.md).
- **F. Repo Process Maturity** (this sub-project) — `SECURITY.md`,
  `CHANGELOG.md`, `ROADMAP.md`, `docs/adr/`.
  [Design spec](docs/superpowers/specs/2026-07-09-repo-process-maturity-design.md).

## Not currently planned

- **A hosted docs site** (mkdocs, Docusaurus, or similar) — this repo's
  six `docs/*.md` files are readable directly on GitHub; building and
  maintaining a generated site with its own hosting and CI publish step
  is a real gap, named here rather than silently omitted, but is not
  currently planned work.
- **A separate `CONTRIBUTING.md`** — `CONTRIBUTORS.md` already
  comprehensively covers the fork/PR flow, SDD process, AI Safety Gate,
  versioning, Gitflow, and code standards a `CONTRIBUTING.md` would;
  there is no plan to duplicate or rename it.

## How this roadmap is maintained

Updated at the end of each sub-project's finishing-a-development-branch
step — the same "update the record when the work actually lands"
discipline this project applies to its own memory/process notes.
