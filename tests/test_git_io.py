from docdrift.git_io import ChangedFile, changed_files, diff, show


def test_changed_files_reports_added_modified_deleted(tiny_repo):
    base = tiny_repo.commit({"a.py": "x = 1\n", "b.py": "y = 2\n"})
    head = tiny_repo.commit({"a.py": "x = 10\n", "b.py": None, "c.py": "z = 3\n"})

    files = changed_files(tiny_repo.path, base, head)

    assert sorted(files, key=lambda f: f.path) == [
        ChangedFile("M", "a.py"),
        ChangedFile("D", "b.py"),
        ChangedFile("A", "c.py"),
    ]


def test_show_reads_old_version_and_returns_none_for_missing_file(tiny_repo):
    first = tiny_repo.commit({"a.py": "timeout = 30\n"})
    tiny_repo.commit({"a.py": "timeout = 60\n"})

    assert show(tiny_repo.path, first, "a.py") == "timeout = 30\n"
    assert show(tiny_repo.path, first, "missing.py") is None


def test_diff_contains_the_changed_line(tiny_repo):
    base = tiny_repo.commit({"a.py": "timeout = 30\n"})
    head = tiny_repo.commit({"a.py": "timeout = 60\n"})

    text = diff(tiny_repo.path, base, head)

    assert "-timeout = 30" in text
    assert "+timeout = 60" in text
