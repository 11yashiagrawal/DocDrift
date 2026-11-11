"""Read-only access to a git repository.

Every function here only *reads* history. Nothing checks out, writes, or
runs code from the repository being analysed.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    """Raised when a git command fails."""


@dataclass(frozen=True)
class ChangedFile:
    """One file touched between two commits."""

    status: str  # "A" added, "M" modified, "D" deleted
    path: str


def run_git(repo: Path, *args: str) -> str:
    """Run `git -C <repo> <args>` and return its standard output as text."""
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotePath=false", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def diff(repo: Path, base: str, head: str) -> str:
    """Unified diff from base to head, with no context lines."""
    return run_git(
        repo, "diff", "--no-color", "--no-ext-diff", "--no-renames",
        "--unified=0", base, head,
    )


def changed_files(repo: Path, base: str, head: str) -> list[ChangedFile]:
    """Files added, modified or deleted between base and head."""
    output = run_git(repo, "diff", "--name-status", "--no-renames", base, head)
    files = []
    for line in output.splitlines():
        status, path = line.split("\t", 1)
        files.append(ChangedFile(status=status, path=path))
    return files


def show(repo: Path, rev: str, path: str) -> str | None:
    """Content of `path` at commit `rev`, or None if it does not exist there."""
    try:
        return run_git(repo, "show", f"{rev}:{path}")
    except GitError:
        return None
