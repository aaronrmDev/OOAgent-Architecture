"""tests/workflow/test_sdd_verify_spec.py — scripts/sdd-verify-spec.sh behavior."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "sdd-verify-spec.sh"


def _resolve_bash() -> str:
    """Resolve a real bash, bypassing Windows' WSL launcher stub.

    On Windows machines with WSL installed, an unqualified ``bash`` passed
    to ``subprocess.run`` resolves to ``C:\\Windows\\System32\\bash.exe``
    (a WSL launcher) rather than Git Bash — Windows' CreateProcess search
    order checks System32 before consulting PATH, regardless of PATH
    ordering. That stub mangles native Windows paths (e.g. drive-letter
    paths with backslashes) passed as argv, causing every test here to
    fail with exit 127 / "No such file or directory" — independent of
    scripts/sdd-verify-spec.sh's own logic. This walks PATH directories in
    order and skips any bash under system32. On Linux CI this is a no-op:
    the first (and only) ``bash`` found is returned unchanged.
    """
    for candidate in os.environ.get("PATH", "").split(os.pathsep):
        exe = shutil.which("bash", path=candidate)
        if exe and "system32" not in exe.lower():
            return exe
    return "bash"


BASH = _resolve_bash()

# `encoding="utf-8"` is passed explicitly to every subprocess.run() call
# below (rather than relying on `text=True`'s locale-default decoding)
# because scripts/sdd-verify-spec.sh emits UTF-8 emoji (e.g. "❌"); on
# Windows the default locale encoding is cp1252, which cannot decode
# those bytes and raises UnicodeDecodeError in the subprocess reader
# thread. This has no effect on Linux CI, which already defaults to UTF-8.


def test_script_passes_on_this_repos_own_specs_directory() -> None:
    result = subprocess.run(
        [BASH, str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_script_reports_orphan_req_with_no_matching_task(tmp_path: Path) -> None:
    specs_dir = tmp_path / "specs" / "999-orphan-example"
    specs_dir.mkdir(parents=True)
    (specs_dir / "spec.md").write_text(
        "- **REQ-1**: something\n  - **AC-1**: criterion\n", encoding="utf-8"
    )
    (specs_dir / "plan.md").write_text("# plan\n", encoding="utf-8")
    (specs_dir / "tasks.md").write_text(
        "- [ ] **TASK-1** does unrelated work\n  - **TEST-1**: `tests/test_x.py::test_y`\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [BASH, str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode != 0
    assert "orphan" in result.stdout.lower()


def test_script_reports_missing_artifact(tmp_path: Path) -> None:
    specs_dir = tmp_path / "specs" / "998-missing-plan"
    specs_dir.mkdir(parents=True)
    (specs_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    (specs_dir / "tasks.md").write_text("# tasks\n", encoding="utf-8")

    result = subprocess.run(
        [BASH, str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode != 0
    assert "missing plan.md" in result.stdout.lower() or "missing plan.md" in result.stderr.lower()


def test_script_exits_zero_when_no_specs_directories_exist(tmp_path: Path) -> None:
    (tmp_path / "specs").mkdir()

    result = subprocess.run(
        [BASH, str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
