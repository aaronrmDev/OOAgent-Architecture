"""tests/workflow/test_gate_makefile.py — .specify/gates/Makefile structural check.

`make` is not installed in every dev environment, so this test checks
Makefile *structure* (every catalog gate has a recipe target) rather than
executing it. Real end-to-end execution happens in CI
(.github/workflows/sdd-gate.yml, ubuntu-latest has make preinstalled).
"""

from __future__ import annotations

from pathlib import Path

from ooagent.workflow.gate_catalog import GATE_TARGETS

MAKEFILE_PATH = Path(__file__).resolve().parents[2] / ".specify" / "gates" / "Makefile"


def test_makefile_exists() -> None:
    assert MAKEFILE_PATH.is_file(), f"expected {MAKEFILE_PATH} to exist"


def test_makefile_defines_every_catalog_gate_target() -> None:
    text = MAKEFILE_PATH.read_text(encoding="utf-8")
    for name in GATE_TARGETS:
        marker = f"\n{name}:"
        assert marker in text, f"Makefile is missing a recipe for gate target {name!r}"


def test_makefile_required_gates_have_non_optional_recipes() -> None:
    text = MAKEFILE_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    for name, spec in GATE_TARGETS.items():
        if not spec.required:
            continue
        idx = next(i for i, line in enumerate(lines) if line.startswith(f"{name}:"))
        recipe_lines = []
        for line in lines[idx + 1 :]:
            if not line.startswith("\t"):
                break
            recipe_lines.append(line)
        recipe_text = "\n".join(recipe_lines)
        assert "_optional" not in recipe_text, (
            f"required gate {name!r} must not use the _optional skip helper"
        )
