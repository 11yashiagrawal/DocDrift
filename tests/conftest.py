"""Shared test helpers: build tiny throwaway git repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


class TinyRepo:
    """A real git repo in a temporary folder, for tests only."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._git("init", "-q")

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.path),
             "-c", "user.name=Test", "-c", "user.email=test@example.com",
             "-c", "commit.gpgsign=false", *args],
            capture_output=True, text=True, check=True,
        ).stdout

    def commit(self, files: dict[str, str | None], message: str = "change") -> str:
        """Write (or delete, when content is None) files, commit, return the hash."""
        for name, content in files.items():
            target = self.path / name
            if content is None:
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", message)
        return self._git("rev-parse", "HEAD").strip()


@pytest.fixture
def tiny_repo(tmp_path: Path) -> TinyRepo:
    return TinyRepo(tmp_path)
