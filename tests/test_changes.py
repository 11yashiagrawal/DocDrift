from docdrift.changes import extract_changes, is_test_file
from docdrift.code_facts import RENAMED


def test_is_test_file():
    assert is_test_file("tests/test_cli.py")
    assert is_test_file("pkg/foo_test.py")
    assert is_test_file("conftest.py")
    assert not is_test_file("src/pkg/cli.py")


def test_extract_changes_reports_rename_with_path_and_commit(tiny_repo):
    base = tiny_repo.commit({
        "cli.py": 'p.add_argument("--max-retries", default=3)\n',
        "tests/test_cli.py": "def test_old():\n    pass\n",
        "README.md": "Use `--max-retries`.\n",
    })
    head = tiny_repo.commit({
        "cli.py": 'p.add_argument("--retry-limit", default=3)\n',
        "tests/test_cli.py": "def test_new():\n    pass\n",
    })

    (result,) = extract_changes(tiny_repo.path, base, head)

    assert result.path == "cli.py"
    assert result.commit == head
    assert result.change.kind == RENAMED
    assert (result.change.old, result.change.new) == ("--max-retries", "--retry-limit")
