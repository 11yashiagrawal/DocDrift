from docdrift.diff_parser import parse_diff
from docdrift.git_io import diff

SIMPLE = """\
diff --git a/cli.py b/cli.py
index 1111111..2222222 100644
--- a/cli.py
+++ b/cli.py
@@ -3 +3 @@ def main():
-    parser.add_argument("--max-retries")
+    parser.add_argument("--retry-limit")
"""


def test_parses_paths_and_line_numbers():
    (file_diff,) = parse_diff(SIMPLE)

    assert file_diff.old_path == "cli.py"
    assert file_diff.new_path == "cli.py"
    (hunk,) = file_diff.hunks
    assert hunk.removed == [(3, '    parser.add_argument("--max-retries")')]
    assert hunk.added == [(3, '    parser.add_argument("--retry-limit")')]


def test_removed_line_that_looks_like_a_file_header_stays_in_the_hunk():
    text = """\
diff --git a/query.sql b/query.sql
--- a/query.sql
+++ b/query.sql
@@ -1,2 +1 @@
--- old comment
 SELECT 1;
"""
    (file_diff,) = parse_diff(text)

    assert file_diff.old_path == "query.sql"
    assert file_diff.hunks[0].removed == [(1, "-- old comment")]


def test_new_and_deleted_files_have_none_paths():
    text = """\
diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+a = 1
+b = 2
diff --git a/old.py b/old.py
deleted file mode 100644
--- a/old.py
+++ /dev/null
@@ -1 +0,0 @@
-gone = True
"""
    new, old = parse_diff(text)

    assert new.old_path is None and new.new_path == "new.py"
    assert new.hunks[0].added == [(1, "a = 1"), (2, "b = 2")]
    assert old.old_path == "old.py" and old.new_path is None
    assert old.hunks[0].removed == [(1, "gone = True")]


def test_real_git_diff_round_trip(tiny_repo):
    base = tiny_repo.commit({"cfg.py": "a = 1\ntimeout = 30\nb = 2\n"})
    head = tiny_repo.commit({"cfg.py": "a = 1\ntimeout = 60\nb = 2\n"})

    (file_diff,) = parse_diff(diff(tiny_repo.path, base, head))

    assert file_diff.hunks[0].removed == [(2, "timeout = 30")]
    assert file_diff.hunks[0].added == [(2, "timeout = 60")]


def test_modified_py_file_is_python():
    (filediff,) = parse_diff(SIMPLE)
    assert filediff.is_python is True


def test_modified_md_file_is_not_python():
    text = """\
diff --git a/EXAMPLES.md b/EXAMPLES.md
--- a/EXAMPLES.md
+++ b/EXAMPLES.md
@@ -1,2 +1 @@
- #Examples
- Here are the given examples of how to use the tool.
+ #Examples
"""
    (filediff,) = parse_diff(text)
    assert filediff.is_python is False


def test_deleted_md_file_is_not_python():
    text = """\
diff --git a/EXAMPLES.md b/EXAMPLES.md
deleted file mode 100644
--- a/EXAMPLES.md
+++ /dev/null
@@ -1,2 +0,0 @@
- #Examples
- Here are the given examples of how to use the tool.
"""
    (filediff,) = parse_diff(text)
    assert filediff.is_python is False


def test_deleted_py_file_is_python():
    text = """\
diff --git a/cli.py b/cli.py
deleted file mode 100644
--- a/cli.py
+++ /dev/null
@@ -1,2 +0,0 @@
- def calculate():
-     return 1 + 1
"""
    (filediff,) = parse_diff(text)
    assert filediff.is_python is True
