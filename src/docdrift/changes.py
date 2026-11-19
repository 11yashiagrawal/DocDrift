"""Stage 1: find meaningful code changes between two commits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from docdrift.code_facts import Change, compare_facts, extract_facts
from docdrift.git_io import changed_files, show


@dataclass(frozen=True)
class CodeChange:
    """A Change plus where it happened: file and commit."""

    change: Change
    path: str
    commit: str


def is_test_file(path: str) -> bool:
    """Tests describe the code; they are not the product docs talk about."""
    p = PurePosixPath(path)
    return (
        "tests" in p.parts
        or "test" in p.parts
        or p.name.startswith("test_")
        or p.name.endswith("_test.py")
        or p.name == "conftest.py"
    )


def extract_changes(repo: Path, base: str, head: str) -> list[CodeChange]:
    """All Changes in non-test Python files between base and head."""
    results: list[CodeChange] = []
    for changed in changed_files(repo, base, head):
        if not changed.path.endswith(".py") or is_test_file(changed.path):
            continue
        if changed.status == "A":
            continue  # a brand-new file can't make existing docs wrong
        old_source = show(repo, base, changed.path) or ""
        new_source = show(repo, head, changed.path) or ""  # "" when deleted
        old_facts = extract_facts(old_source)
        new_facts = extract_facts(new_source)
        if old_facts is None or new_facts is None:
            continue  # unparseable Python: text fallback comes in a later block
        for change in compare_facts(old_facts, new_facts):
            results.append(CodeChange(change, changed.path, head))
    return results
