"""tests/workflow/test_sdd_verify_spec.py — scripts/sdd-verify-spec.sh behavior."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "sdd-verify-spec.sh"

# Path substrings that identify a WSL-launcher-family stub rather than a
# real POSIX-capable bash. Windows ships at least two of these: the
# System32 ``bash.exe`` WSL launcher, and an "App Execution Alias" stub
# under WindowsApps (both under a ``...\Microsoft\...`` tree). Neither can
# execute a real shell script; both must be rejected even though only one
# contains "system32".
_WSL_STUB_MARKERS = ("system32", "windowsapps", "microsoft")

# Well-known Git-for-Windows install locations. Git for Windows' default
# installer only adds ``Git\cmd`` to PATH (which has no bash.exe at all),
# so the real interpreter at ``Git\bin\bash.exe`` / ``Git\usr\bin\bash.exe``
# is frequently unreachable via a PATH-only scan and must be probed
# explicitly as a fallback.
_GIT_BASH_FALLBACKS = (
    r"Git\bin\bash.exe",
    r"Git\usr\bin\bash.exe",
)


def _bash_actually_works(candidate: str) -> bool:
    """Self-validate a candidate by actually invoking it.

    A working self-test catches launcher stubs that a path-substring
    blocklist would miss entirely (e.g. a third, differently-located WSL
    alias future Windows builds might add).
    """
    try:
        result = subprocess.run(
            [candidate, "-c", "echo ok"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "ok"


def _resolve_bash() -> str:
    """Resolve a real, working bash, bypassing Windows' WSL launcher stubs.

    On Windows machines with WSL (or just the "App Execution Alias" WSL
    stub) installed, an unqualified ``bash`` passed to ``subprocess.run``
    can resolve to a launcher stub (``C:\\Windows\\System32\\bash.exe`` or
    ``...\\Microsoft\\WindowsApps\\bash.exe``) rather than Git Bash —
    Windows' CreateProcess search order checks these locations ahead of
    PATH-listed directories, regardless of PATH ordering. Those stubs
    mangle native Windows paths (e.g. drive-letter paths with backslashes)
    passed as argv, causing every test here to fail with exit 127 / "No
    such file or directory" — independent of scripts/sdd-verify-spec.sh's
    own logic.

    Strategy, in order:
      1. Walk PATH directories, skip any candidate whose path contains a
         known WSL-stub marker, and self-validate (actually invoke) the
         rest — accept the first one that really runs a shell command.
      2. If PATH yields nothing usable (Git for Windows' default installer
         only adds ``Git\\cmd`` to PATH, which has no bash.exe at all),
         probe well-known Git-for-Windows install locations directly.
      3. Fall back to the unqualified ``"bash"`` name.

    On Linux CI (and any non-Windows platform) this is a deliberate no-op:
    none of the above runs, and plain ``"bash"`` — already correct there —
    is returned unchanged.
    """
    if sys.platform != "win32":
        return "bash"

    for candidate_dir in os.environ.get("PATH", "").split(os.pathsep):
        exe = shutil.which("bash", path=candidate_dir)
        if not exe:
            continue
        lowered = exe.lower()
        if any(marker in lowered for marker in _WSL_STUB_MARKERS):
            continue
        if _bash_actually_works(exe):
            return exe

    for env_var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        base = os.environ.get(env_var)
        if not base:
            continue
        for rel in _GIT_BASH_FALLBACKS:
            exe = os.path.join(base, rel)
            if os.path.isfile(exe) and _bash_actually_works(exe):
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
