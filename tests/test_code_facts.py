from docdrift.code_facts import (
    DEFAULT_CHANGED,
    HELP_OR_BODY_CHANGED,
    REMOVED,
    RENAMED,
    SIGNATURE_CHANGED,
    compare_facts,
    extract_facts,
)


def kinds(old_source: str, new_source: str) -> list[tuple[str, str, str, str]]:
    """Compare two sources and return (kind, symbol, old, new) for each change."""
    changes = compare_facts(extract_facts(old_source), extract_facts(new_source))
    return [(c.kind, c.symbol, c.old, c.new) for c in changes]


def test_extracts_function_params_and_defaults():
    facts = extract_facts("def connect(host, port=80, *, timeout=30):\n    pass\n")

    fact = facts["connect"]
    assert fact.kind == "function"
    assert fact.params == ("host", "port", "timeout")
    assert fact.defaults == (("port", "80"), ("timeout", "30"))
    assert fact.line == 1


def test_extracts_flags_methods_constants_and_skips_private():
    source = '''
TIMEOUT = 30
_secret = 1

class Client:
    def send(self, data):
        pass
    def _helper(self):
        pass

def build(parser):
    parser.add_argument("-r", "--max-retries", type=int, default=3, help="Retry count")
'''
    facts = extract_facts(source)

    assert set(facts) == {"TIMEOUT", "Client", "Client.send", "build", "--max-retries"}
    assert facts["Client.send"].params == ("data",)
    assert facts["--max-retries"].defaults == (("default", "3"),)
    assert facts["--max-retries"].help == "Retry count"


def test_unparseable_source_returns_none():
    assert extract_facts("def broken(:\n") is None


def test_renamed_flag():
    old = 'p.add_argument("--max-retries", type=int, default=3)\n'
    new = 'p.add_argument("--retry-limit", type=int, default=3)\n'

    assert kinds(old, new) == [(RENAMED, "--max-retries", "--max-retries", "--retry-limit")]


def test_removed_function():
    old = "def export_csv(path):\n    pass\n\ndef keep():\n    pass\n"
    new = "def keep():\n    pass\n"

    assert kinds(old, new) == [(REMOVED, "export_csv", "export_csv", "")]


def test_changed_default_of_flag_and_function_and_constant():
    old = 'TIMEOUT = 30\ndef connect(t=30):\n    pass\np.add_argument("--timeout", default=30)\n'
    new = 'TIMEOUT = 60\ndef connect(t=60):\n    pass\np.add_argument("--timeout", default=60)\n'

    assert sorted(kinds(old, new)) == [
        (DEFAULT_CHANGED, "--timeout", "default=30", "default=60"),
        (DEFAULT_CHANGED, "TIMEOUT", "value=30", "value=60"),
        (DEFAULT_CHANGED, "connect", "t=30", "t=60"),
    ]


def test_changed_signature():
    old = "def connect(host, port):\n    pass\n"
    new = "def connect(url):\n    pass\n"

    assert kinds(old, new) == [(SIGNATURE_CHANGED, "connect", "connect(host, port)", "connect(url)")]


def test_same_name_new_behaviour_is_help_or_body_changed():
    old = 'p.add_argument("--preview", action="store_true", help="Enable new string style")\n'
    new = 'p.add_argument("--preview", action="store_true", help="Enable all unstable features")\n'

    assert kinds(old, new) == [
        (HELP_OR_BODY_CHANGED, "--preview", "Enable new string style", "Enable all unstable features")
    ]


def test_formatting_and_docstring_only_changes_are_ignored():
    old = 'def f(a):\n    """Old words."""\n    return a+1\n'
    new = 'def f(a):\n    """New words."""\n\n    return (a + 1)  # comment\n'

    assert kinds(old, new) == []


def test_new_symbols_are_not_reported():
    assert kinds("def a():\n    pass\n", "def a():\n    pass\n\ndef b():\n    pass\n") == []


def test_removed_lists_new_names_of_same_kind_as_possible_replacements():
    old = 'def export_csv(path):\n    pass\n'
    new = 'def export_table(path, fmt="csv"):\n    pass\n\nTIMEOUT = 30\n'

    assert kinds(old, new) == [(REMOVED, "export_csv", "export_csv", "export_table")]


def test_rename_with_changed_default_is_removed_with_hint():
    old = 'p.add_argument("--max-retries", default=3)\n'
    new = 'p.add_argument("--retry-limit", default=5)\n'

    assert kinds(old, new) == [(REMOVED, "--max-retries", "--max-retries", "--retry-limit")]


def test_extracts_annotated_constant():
    facts = extract_facts("TIMEOUT: int = 30\n")
    assert facts["TIMEOUT"].kind == "constant"
    assert facts["TIMEOUT"].defaults == (("value", "30"),)

def test_annotated_constant_with_no_value_not_extracted():
    facts = extract_facts("TIMEOUT: int\n")
    assert facts == {}
    