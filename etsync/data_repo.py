"""Git-based data repository for tracking sync history."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(data_dir: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command inside the data directory."""
    return subprocess.run(
        ["git", *args],
        cwd=str(data_dir),
        capture_output=True,
        text=True,
        check=check,
    )


def ensure_repo(data_dir: Path) -> None:
    """Initialize a git repo in the data directory if one doesn't exist."""
    data_dir.mkdir(parents=True, exist_ok=True)
    git_dir = data_dir / ".git"
    if not git_dir.exists():
        _run_git(data_dir, "init")
        _run_git(data_dir, "commit", "--allow-empty", "-m", "init: empty data repo")


def commit_sync(data_dir: Path, *, count: int, synced_at: str) -> bool:
    """Stage all changes and commit with a sync message.

    Returns True if a commit was created, False if there was nothing to commit.
    """
    ensure_repo(data_dir)

    _run_git(data_dir, "add", "-A")

    # Check if there's anything staged
    result = _run_git(data_dir, "diff", "--cached", "--quiet", check=False)
    if result.returncode == 0:
        return False

    message = f"sync: {count} listings @ {synced_at}"
    _run_git(data_dir, "commit", "-m", message)
    return True


def diff_last_sync(data_dir: Path) -> str:
    """Return the diff between the last two sync commits."""
    ensure_repo(data_dir)

    result = _run_git(data_dir, "rev-list", "--count", "HEAD", check=False)
    if result.returncode != 0:
        return "No sync history found."

    commit_count = int(result.stdout.strip())
    if commit_count < 2:
        return "Only one sync recorded. No previous sync to compare against."

    diff_result = _run_git(data_dir, "diff", "HEAD~1..HEAD", check=False)
    output = diff_result.stdout.strip()
    return output if output else "No changes between last two syncs."
