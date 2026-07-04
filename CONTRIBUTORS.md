# Contributors

OOAgent is an open-source project maintained under the MIT License.
Contributions of all kinds are welcome — code, documentation, context implementations,
plugin packages, adapter backends, and bug reports.

---

## Core Maintainers

| Name | GitHub | Role |
|---|---|---|
| Aaron Rodriguez | [@aaronrmDev](https://github.com/aaronrmDev) | Founder & Lead Architect |

---

## How to Contribute

### 1. Fork → Feature Branch → PR

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/<your-handle>/OOAgent-Architecture.git
cd OOAgent-Architecture
git checkout develop
git checkout -b feature/<scope>/<short-description>
```

All PRs target `develop`. See the [Gitflow diagram](#gitflow) below.

### 2. Follow Spec Driven Development

This project is **specification-first**. Before writing implementation code:

1. Draft the interface change in `src/ooagent/core/protocols.py` (or leave it unchanged)
2. Write conformance tests in `tests/conformance/` (§17 CLAUDE.md)
3. Implement the feature
4. Run the full CI gate locally:

```bash
uv run mypy --strict
bash scripts/ai-safety-gate.sh --verbose
bash scripts/conformance-check.sh
uv run pytest tests/ -v
```

### 3. AI Safety Gate

Every contribution **must pass all 10 AI Safety Guards** before merge.
The guards are not advisory — they map directly to documented AI disasters
that caused real harm. See `scripts/ai-safety-gate.sh` for details.

### 4. Versioning

This project uses `YYYY.MM.NN` versioning:

- **YYYY** — 4-digit year of the release
- **MM** — 2-digit month (`01`–`12`)
- **NN** — 2-digit sequential build within the month (`01`–`99`)

Example: `2026.06.01` is the first release of June 2026.

Breaking changes to `core/protocols.py` interfaces require a new month or year increment.

---

## Gitflow

```
master ──────────────────────────────────────── (production releases only)
  │                              ▲
  │ hotfix/*                     │ release/YYYY.MM.NN
  ▼                              │
develop ─────────────────────────────────────── (integration branch)
  ▲           ▲
  │feature/*  │feature/*
```

| Branch | Purpose | Base | Merges into |
|---|---|---|---|
| `master` | Production releases | — | — |
| `develop` | Integration | `master` | `master` via `release/` |
| `feature/*` | New capabilities | `develop` | `develop` |
| `release/YYYY.MM.NN` | Release preparation | `develop` | `master` + `develop` |
| `hotfix/*` | Emergency fixes | `master` | `master` + `develop` |

---

## What You Can Contribute

### Domain Contexts (`contexts/`)

Implement `IDomainContext` for a new problem domain. Required deliverables:
- `contexts/<domain>/__init__.py` — implementation
- `contexts/<domain>/CONTEXT.md` — domain specification (§14 CLAUDE.md)
- Conformance tests (§17 CLAUDE.md)

### LLM Adapters (`adapters/llm/`)

Implement `ILLMClient` for a new inference backend. Required deliverables:
- `adapters/llm/<vendor>.py`
- Conformance tests using `StubLLMClient` as reference
- No changes to `core/`

### Tools (`adapters/tools/` or `plugins/<name>/`)

Implement `ITool` extending `BaseTool`. Required deliverables:
- Tool implementation
- Conformance tests (valid args, ToolExecutionError, to_vendor_spec)
- If bundled as a plugin: implement `IPlugin` wrapping the tool

### Plugins (`plugins/`)

Implement `IPlugin` extending `AbstractPlugin`. Required deliverables:
- `plugins/<name>/__init__.py`
- `on_register()`, `on_dispose()`, `contributes()`
- Only import from `core/protocols.py` (never core implementation files)

---

## Code Standards

- Python: `mypy --strict` — no untyped `def`s, no `# type: ignore` without justification
- Zero comments on self-explanatory code; one-line max on non-obvious logic
- No hardcoded secrets — environment variables only
- Every async function must handle errors explicitly
- Output discipline: numbers carry `value + unit + SourceTag` (§15 CLAUDE.md)

---

## Contributor License Agreement

By submitting a pull request, you agree that your contribution is licensed
under the MIT License and that you have the right to submit it.

---

## Recognition

All merged contributors are listed in this file.
Significant contributions are highlighted in the GitHub Release notes.

---

*Thank you for making AI engineering safer and more principled.*
