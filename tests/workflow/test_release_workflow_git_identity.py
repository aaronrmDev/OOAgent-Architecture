"""tests/workflow/test_release_workflow_git_identity.py — release.yml git-identity check.

Regression test for specs/002-release-workflow-git-identity/. The
"Create git tag" step in .github/workflows/release.yml failed on the
v2026.07.01 release with "fatal: empty ident name" because the GitHub
Actions runner has no default git user.name/user.email, and `git tag -a`
(an annotated tag) requires a non-empty committer identity. This test
checks workflow *structure* (the fix is present, and ordered correctly)
rather than executing the workflow — real end-to-end execution only
happens on GitHub Actions when a release/** branch is pushed.
"""

from __future__ import annotations

from pathlib import Path

RELEASE_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release.yml"
)


def _create_git_tag_step_text() -> str:
    text = RELEASE_WORKFLOW_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if "name: Create git tag" in line)
    step_lines = []
    for line in lines[start + 1 :]:
        if "- name:" in line:
            break
        step_lines.append(line)
    return "\n".join(step_lines)


def test_release_workflow_exists() -> None:
    assert RELEASE_WORKFLOW_PATH.is_file(), f"expected {RELEASE_WORKFLOW_PATH} to exist"


def test_create_git_tag_step_configures_identity_before_tagging() -> None:
    step_text = _create_git_tag_step_text()

    name_idx = step_text.find('git config user.name "github-actions[bot]"')
    email_idx = step_text.find(
        'git config user.email "github-actions[bot]@users.noreply.github.com"'
    )
    tag_idx = step_text.find("git tag -a")

    assert name_idx != -1, "Create git tag step is missing `git config user.name`"
    assert email_idx != -1, "Create git tag step is missing `git config user.email`"
    assert tag_idx != -1, "Create git tag step is missing `git tag -a`"
    assert name_idx < tag_idx, "git config user.name must run before git tag -a"
    assert email_idx < tag_idx, "git config user.email must run before git tag -a"
