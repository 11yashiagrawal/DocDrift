"""Parse unified diffs (the text `git diff` prints) into Python objects."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class Hunk:
    """One block of changes. Line numbers are 1-based, as editors show them."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    removed: list[tuple[int, str]] = field(default_factory=list)
    added: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class FileDiff:
    """All hunks for one file. A path is None when the file did not exist."""

    old_path: str | None
    new_path: str | None
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def is_python(self) -> bool:
        """Return True if the file is a Python source file."""
        path = self.new_path or self.old_path
        return path is not None and path.endswith(".py")


def _strip_prefix(raw: str) -> str | None:
    """'a/src/x.py' -> 'src/x.py'; '/dev/null' -> None."""
    if raw == "/dev/null":
        return None
    return raw[2:]


def parse_diff(text: str) -> list[FileDiff]:
    """Turn `git diff` output into FileDiff objects.

    Inside a hunk, lines are consumed by the counts in its @@ header, never by
    their first character. A removed line such as '-- comment' would otherwise
    look like a '---' file header.
    """
    files: list[FileDiff] = []
    current: FileDiff | None = None
    hunk: Hunk | None = None
    old_left = new_left = 0
    old_line = new_line = 0

    for line in text.splitlines():
        if hunk is not None and (old_left > 0 or new_left > 0):
            if line.startswith("\\"):  # "\ No newline at end of file"
                continue
            tag, body = line[:1], line[1:]
            if tag == "-":
                hunk.removed.append((old_line, body))
                old_line += 1
                old_left -= 1
            elif tag == "+":
                hunk.added.append((new_line, body))
                new_line += 1
                new_left -= 1
            else:  # context line: present on both sides
                old_line += 1
                new_line += 1
                old_left -= 1
                new_left -= 1
            continue

        if line.startswith("diff --git "):
            current = FileDiff(old_path=None, new_path=None)
            files.append(current)
            hunk = None
        elif line.startswith("--- ") and current is not None:
            current.old_path = _strip_prefix(line[4:])
        elif line.startswith("+++ ") and current is not None:
            current.new_path = _strip_prefix(line[4:])
        elif (match := HUNK_HEADER.match(line)) and current is not None:
            old_start, old_count, new_start, new_count = match.groups()
            hunk = Hunk(
                old_start=int(old_start),
                old_count=int(old_count) if old_count is not None else 1,
                new_start=int(new_start),
                new_count=int(new_count) if new_count is not None else 1,
            )
            current.hunks.append(hunk)
            old_left, new_left = hunk.old_count, hunk.new_count
            old_line, new_line = hunk.old_start, hunk.new_start
    return files
